#frondend/streamlit.py

import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import io
import plotly.express as px
import plotly.graph_objects as go
import socket
import time

# ---------------- Page config ----------------
st.set_page_config(page_title="Expense Forecaster", layout="wide", page_icon="💸")

# ---------------- API base ----------------
def get_backend_url():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        if result == 0:
            return "http://localhost:5000"
    except:
        pass
    return "http://192.168.1.49:5000"

API_BASE = get_backend_url()

# ---------------- Optimized Helpers ----------------
def safe_json(resp):
    try:
        return resp.json()
    except:
        return None

def api_request(method, path, token=None, json=None, files=None, timeout=10):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = API_BASE.rstrip("/") + path
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == "POST":
            if files:
                response = requests.post(url, headers=headers, files=files, data=json, timeout=timeout)
            else:
                response = requests.post(url, headers=headers, json=json, timeout=timeout)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=timeout)
        else:
            return None
        return response
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")
        return None

# ---------------- Optimized Data Management ----------------
def get_user_transactions():
    """Get transactions with cache and timestamp to prevent loops"""
    if not st.session_state.get("token"):
        return pd.DataFrame()
    
    cache_key = "user_transactions"
    timestamp_key = "user_transactions_timestamp"
    
    # Return cached data if less than 120 seconds old
    current_time = time.time()
    if (cache_key in st.session_state and 
        timestamp_key in st.session_state and
        current_time - st.session_state[timestamp_key] < 120):
        return st.session_state[cache_key]
    
    # Fetch from backend
    r = api_request("GET", "/transactions", token=st.session_state.token)
    
    if not r or r.status_code != 200:
        return pd.DataFrame()
    
    txs = safe_json(r) or []
    if not txs:
        df = pd.DataFrame(columns=['date', 'amount', 'description', 'category', 'type'])
    else:
        df = pd.DataFrame(txs)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            df = df.dropna(subset=['date', 'amount'])
    
    # Cache with timestamp
    st.session_state[cache_key] = df
    st.session_state[timestamp_key] = current_time
    return df

def get_user_overview():
    """Get overview with cache"""
    if not st.session_state.get("token"):
        return None
    
    cache_key = "user_overview"
    timestamp_key = "user_overview_timestamp"
    
    current_time = time.time()
    if (cache_key in st.session_state and 
        timestamp_key in st.session_state and
        current_time - st.session_state[timestamp_key] < 120):
        return st.session_state[cache_key]
    
    r = api_request("GET", "/reports/overview", token=st.session_state.token)
    
    if not r or r.status_code != 200:
        df = get_user_transactions()
        if df.empty:
            overview = {"total_income": 0, "total_expense": 0, "net_balance": 0, "recent_transactions": 0}
        else:
            total_income = df[df['type'] == 'income']['amount'].sum()
            total_expense = df[df['type'] == 'expense']['amount'].sum()
            recent_count = len(df[df['date'] >= (datetime.now() - timedelta(days=30))])
            overview = {
                "total_income": float(total_income),
                "total_expense": float(total_expense),
                "net_balance": float(total_income - total_expense),
                "recent_transactions": int(recent_count)
            }
    else:
        overview = safe_json(r) or {}
    
    st.session_state[cache_key] = overview
    st.session_state[timestamp_key] = current_time
    return overview

def get_user_category_report(days=30):
    """Get category report with cache"""
    if not st.session_state.get("token"):
        return None
    
    cache_key = f"user_category_{days}"
    timestamp_key = f"user_category_{days}_timestamp"
    
    current_time = time.time()
    if (cache_key in st.session_state and 
        timestamp_key in st.session_state and
        current_time - st.session_state[timestamp_key] < 120):
        return st.session_state[cache_key]
    
    r = api_request("GET", f"/reports/category?days={days}", token=st.session_state.token)
    
    if not r or r.status_code != 200:
        df = get_user_transactions()
        if df.empty:
            report = {"total_expense": 0, "by_category": []}
        else:
            start_date = datetime.now() - timedelta(days=days)
            expense_df = df[(df['date'] >= start_date) & (df['type'] == 'expense')]
            if expense_df.empty:
                report = {"total_expense": 0, "by_category": []}
            else:
                category_totals = expense_df.groupby('category')['amount'].sum().reset_index()
                total_expense = category_totals['amount'].sum()
                category_totals['percent'] = (category_totals['amount'] / total_expense * 100).round(2)
                report = {
                    "total_expense": float(total_expense),
                    "by_category": category_totals.rename(columns={'amount': 'total'}).to_dict('records')
                }
    else:
        report = safe_json(r) or {}
    
    st.session_state[cache_key] = report
    st.session_state[timestamp_key] = current_time
    return report

def clear_user_cache():
    """Clear all cached data for current user"""
    cache_keys = [
        "user_transactions", "user_transactions_timestamp",
        "user_overview", "user_overview_timestamp",
        "user_category_30", "user_category_30_timestamp",
        "user_category_90", "user_category_90_timestamp",
        "goals_data", "goals_last_fetch",
        "forecast_categories", "categories_last_fetch",
        "forecast_result"
    ]
    
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]

# ---------------- Authentication ----------------
def handle_auth(email, password, is_register=False):
    endpoint = "/auth/register" if is_register else "/auth/login"
    r = api_request("POST", endpoint, json={"email": email, "password": password})
    
    if not r or r.status_code not in [200, 201]:
        st.error("❌ Authentication failed. Check your credentials.")
        return False
    
    payload = safe_json(r) or {}
    token = payload.get("access_token")
    if token:
        st.session_state.token = token
        st.session_state.user_email = payload.get("email", email)
        st.success("✅ Login successful!")
        clear_user_cache()  # Clear cache on login
        return True
    return False

# ---------------- Session State Management ----------------
def init_session_state():
    if "token" not in st.session_state:
        st.session_state.token = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "last_added_tx" not in st.session_state:
        st.session_state.last_added_tx = None
    if "selected_goal_id" not in st.session_state:
        st.session_state.selected_goal_id = None
    if "coaching_data" not in st.session_state:
        st.session_state.coaching_data = None
    if "coaching_loading" not in st.session_state:
        st.session_state.coaching_loading = False

init_session_state()

# ---------------- CSS ----------------
st.markdown("""
    <style>
    .block-container { padding: 1rem 1rem; }
    .stButton>button { height: 44px; font-size: 15px; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 4px solid #007bff; }
    </style>
""", unsafe_allow_html=True)

# ---------------- Optimized Sidebar ----------------
def render_sidebar():
    with st.sidebar:
        st.title("🔐 Account")
        
        if st.session_state.token:
            st.success(f"Logged in as **{st.session_state.user_email}**")
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
                clear_user_cache()
                st.session_state.token = None
                st.session_state.user_email = None
                st.session_state.last_added_tx = None
                st.session_state.selected_goal_id = None
                st.session_state.coaching_data = None
                st.success("✅ Logged out successfully!")
        else:
            auth_tab = st.radio("Action", ["Login", "Register"], horizontal=True, key="auth_tab")
            email = st.text_input("📧 Email", key="email_input")
            password = st.text_input("🔒 Password", type="password", key="password_input")
            
            if st.button("Submit", use_container_width=True, key="auth_submit"):
                if email and password:
                    handle_auth(email, password, auth_tab == "Register")
                else:
                    st.warning("Please enter both email and password")

        st.markdown("---")
        st.header("📊 Quick Insights")
        
        if st.session_state.token:
            overview = get_user_overview()
            if overview:
                col1, col2 = st.columns(2)
                col1.metric("💰 Expenses", f"₹{overview.get('total_expense', 0):,.2f}")
                col2.metric("💵 Income", f"₹{overview.get('total_income', 0):,.2f}")
                st.caption(f"📈 {overview.get('recent_transactions', 0)} transactions in last 30 days")
            else:
                st.info("No transactions yet")

# ---------------- Optimized Transactions Tab ----------------
def render_transactions():
    st.header("💳 Transaction Management")
    
    if not st.session_state.token:
        st.info("🔐 Please login to manage transactions")
        return

    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.expander("➕ Add Transaction", expanded=True):
            if st.session_state.last_added_tx:
                tx = st.session_state.last_added_tx
                st.success(f"✅ **Added:** {tx['description']} - ₹{tx['amount']:,.2f} ({tx['category']})")
                st.session_state.last_added_tx = None
            
            with st.form("manual_add", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    t_date = st.date_input("📅 Date", value=date.today(), key="tx_date")
                    t_amount = st.number_input("💰 Amount", value=0.0, format="%.2f", step=100.0, key="tx_amount")
                with col_b:
                    t_type = st.selectbox("🔸 Type", ["expense", "income"], key="tx_type")
                    t_desc = st.text_input("📝 Description", placeholder="e.g., Netflix subscription", key="tx_desc")
                
                categories = ["", "Groceries", "Transport", "Dining", "Rent", "Utilities", "Entertainment", 
                             "Healthcare", "Education", "Shopping", "Travel", "Miscellaneous"]
                t_cat = st.selectbox("Choose category (AI auto-categorizes if empty):", categories, key="tx_cat")
                
                submitted = st.form_submit_button("💾 Add Transaction", use_container_width=True)
                if submitted:
                    if t_amount <= 0:
                        st.error("❌ Amount must be greater than 0")
                    else:
                        payload = {
                            "date": t_date.isoformat(), 
                            "amount": float(t_amount), 
                            "description": t_desc, 
                            "type": t_type
                        }
                        if t_cat:
                            payload["category"] = t_cat
                        
                        r = api_request("POST", "/transactions", token=st.session_state.token, json=payload)
                        if r and r.status_code in [200, 201]:
                            response_data = safe_json(r) or {}
                            st.session_state.last_added_tx = {
                                "description": t_desc,
                                "amount": float(t_amount),
                                "category": response_data.get("category", "Uncategorized")
                            }
                            clear_user_cache()
                        else:
                            st.error("❌ Failed to add transaction")

    with col2:
        with st.expander("📁 Bulk Upload"):
            uploaded = st.file_uploader("Choose CSV file", type=["csv"], key="bulk_upload")
            if uploaded:
                try:
                    preview = pd.read_csv(uploaded)
                    st.success(f"📊 {len(preview)} rows detected")
                    st.info("💡 AI will auto-categorize descriptions")
                    
                    if st.button("🚀 Upload to Account", use_container_width=True, key="upload_btn"):
                        with st.spinner("Processing with AI..."):
                            files = {'file': (uploaded.name, uploaded.getvalue())}
                            r = api_request("POST", "/transactions/bulk", token=st.session_state.token, files=files, timeout=120)
                            
                            if r and r.status_code == 200:
                                result = safe_json(r) or {}
                                st.success(f"✅ {result.get('inserted', 0)} transactions processed!")
                                clear_user_cache()
                            else:
                                st.error("❌ Upload failed")
                except Exception as e:
                    st.error(f"❌ Error reading CSV: {e}")

    # Transaction List
    st.subheader("📋 Your Transactions")
    df = get_user_transactions()
    
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            preset = st.selectbox("⏰ Time Period", 
                                ["Last 30 days", "Last 90 days", "This month", "This year", "All time"], 
                                key="time_period")
        with col2:
            search_term = st.text_input("🔍 Search descriptions", key="search_term")
        with col3:
            sort_by = st.selectbox("📊 Sort by", 
                                 ["Date (newest)", "Date (oldest)", "Amount (high)", "Amount (low)"], 
                                 key="sort_by")

        # Filter data
        today = date.today()
        if preset == "Last 30 days":
            start_date = today - timedelta(days=30)
            end_date = today
        elif preset == "Last 90 days":
            start_date = today - timedelta(days=90)
            end_date = today
        elif preset == "This month":
            start_date = today.replace(day=1)
            end_date = today
        elif preset == "This year":
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            start_date = df['date'].min().date() if not df.empty else today
            end_date = df['date'].max().date() if not df.empty else today
        
        mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
        filtered_df = df.loc[mask].copy()
        
        if search_term:
            filtered_df = filtered_df[filtered_df['description'].str.contains(search_term, case=False, na=False)]
        
        # Sort data
        sort_map = {
            "Date (newest)": ('date', False),
            "Date (oldest)": ('date', True),
            "Amount (high)": ('amount', False),
            "Amount (low)": ('amount', True)
        }
        sort_col, sort_asc = sort_map[sort_by]
        filtered_df = filtered_df.sort_values(sort_col, ascending=sort_asc)
        
        # Display data
        display_df = filtered_df.head(50).copy()
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        display_df['amount'] = display_df['amount'].map(lambda x: f"₹{x:,.2f}")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.caption(f"Showing {len(display_df)} of {len(filtered_df)} transactions")
        
        if st.button("🔄 Refresh Data", use_container_width=True, key="refresh_tx"):
            clear_user_cache()
    else:
        st.info("💳 No transactions found. Add your first transaction above!")

# ---------------- Optimized Dashboard Tab ----------------
def render_dashboard():
    st.header("📊 Dashboard Overview")
    
    if not st.session_state.token:
        st.info("🔐 Please login to view dashboard")
        return
        
    # Use cached data to prevent loops
    overview = get_user_overview()
    df = get_user_transactions()
    
    if df.empty:
        st.info("💳 No transactions found. Add your first transaction!")
        return
        
    # Financial Summary
    st.subheader("💰 Financial Summary")
    
    if overview:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Income", f"₹{overview.get('total_income', 0):,.2f}")
        col2.metric("Expenses", f"₹{overview.get('total_expense', 0):,.2f}", delta_color="inverse")
        col3.metric("Net Balance", f"₹{overview.get('net_balance', 0):,.2f}", 
                   delta_color="normal" if overview.get('net_balance', 0) >= 0 else "inverse")
        col4.metric("Recent Tx", overview.get('recent_transactions', 0))

    # Recent Transactions
    st.subheader("🕒 Recent Transactions")
    recent_tx = df.sort_values('date', ascending=False).head(8)
    if not recent_tx.empty:
        display_data = recent_tx[['date', 'description', 'amount', 'category']].copy()
        display_data['date'] = display_data['date'].dt.strftime('%Y-%m-%d')
        display_data['amount'] = display_data['amount'].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(display_data.rename(columns={
            'date': 'Date', 'description': 'Description', 'amount': 'Amount', 'category': 'Category'
        }), use_container_width=True, hide_index=True)
    else:
        st.info("No recent transactions")

    # Category Spending
    category_data = get_user_category_report(days=90)
    
    if category_data and category_data.get("by_category"):
        by_category = category_data["by_category"]
        total_expense = category_data.get("total_expense", 0)
        
        if total_expense > 0:
            # Convert to DataFrame for visualization
            cat_df = pd.DataFrame(by_category)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig_pie = px.pie(
                    cat_df, 
                    names='category', 
                    values='total', 
                    title="Your AI-Categorized Expense Distribution",
                    hole=0.4
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.write("**Your Category Breakdown**")
                breakdown = cat_df.copy()
                breakdown['percentage'] = (breakdown['total'] / total_expense * 100).round(1)
                breakdown['total'] = breakdown['total'].map(lambda x: f"₹{x:,.2f}")
                
                st.dataframe(
                    breakdown.rename(columns={'category': 'Category', 'total': 'Amount', 'percentage': '%'}),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("No expense data in your account")
    else:
        st.info("No categorized expense data in your account")

# ---------------- Optimized Reports Tab ----------------
def render_reports():
    st.header("📈 Spending Reports & Analytics")
    
    if not st.session_state.token:
        st.info("🔐 Please login to view reports")
        return
        
    # Use cached data
    df = get_user_transactions()
    
    if df.empty:
        st.info("📊 No transaction data for reporting")
        return
        
    # Report Period
    report_preset = st.selectbox("📅 Report Period", 
                               ["Last 3 months", "Last 6 months", "This year", "All time"],
                               key="report_period")
    
    # Date range
    today = date.today()
    if report_preset == "Last 3 months":
        days_back = 90
    elif report_preset == "Last 6 months":
        days_back = 180
    elif report_preset == "This year":
        days_back = (today - today.replace(month=1, day=1)).days
    else:
        days_back = (df['date'].max().date() - df['date'].min().date()).days if not df.empty else 365
    
    start_date = today - timedelta(days=days_back)
    end_date = today
    st.caption(f"📅 Showing data from {start_date} to {end_date}")
    
    # Filter data
    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
    report_df = df.loc[mask].copy()
    
    if report_df.empty:
        st.info("No transactions in selected period")
        return
    
    # Monthly Summary
    st.subheader("📅 Monthly Summary")
    if not report_df.empty:
        report_df.loc[:, 'month'] = report_df['date'].dt.to_period('M')
        monthly = report_df.groupby(['month', 'type'])['amount'].sum().unstack(fill_value=0)
        monthly['income'] = monthly.get('income', 0)
        monthly['expense'] = monthly.get('expense', 0)
        monthly['net'] = monthly['income'] - monthly['expense']
        monthly = monthly.reset_index()
        monthly['month'] = monthly['month'].astype(str)
        
        fig_trend = px.line(monthly, x='month', y=['income', 'expense'],
                          title="Monthly Income vs Expenses")
        fig_trend.update_layout(template="plotly_white")
        st.plotly_chart(fig_trend, use_container_width=True)

    # Category Report
    st.subheader("📊 Category Report")
    category_data = get_user_category_report(days=days_back)
    
    if category_data and category_data.get("by_category"):
        by_category = category_data["by_category"]
        total_expense = category_data.get("total_expense", 0)
        
        if total_expense > 0:
            cat_df = pd.DataFrame(by_category)
            cat_df = cat_df.sort_values('total', ascending=True)
            
            col1, col2 = st.columns(2)
            with col1:
                fig_bar = px.bar(cat_df, x='total', y='category', orientation='h',
                               title="Spending by Category")
                fig_bar.update_layout(template="plotly_white", showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                breakdown = cat_df.sort_values('total', ascending=False).copy()
                breakdown['percentage'] = (breakdown['total'] / total_expense * 100).round(1)
                breakdown['total'] = breakdown['total'].map(lambda x: f"₹{x:,.2f}")
                st.dataframe(breakdown.rename(columns={
                    'category': 'Category', 'total': 'Amount', 'percentage': '%'
                }), use_container_width=True, hide_index=True)

    # Summary Metrics
    st.subheader("💰 Summary")
    total_income = report_df[report_df['type']=='income']['amount'].sum()
    total_expense = report_df[report_df['type']=='expense']['amount'].sum()
    net_balance = total_income - total_expense
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Income", f"₹{total_income:,.2f}")
    col2.metric("Expenses", f"₹{total_expense:,.2f}")
    col3.metric("Net Balance", f"₹{net_balance:,.2f}", 
               delta_color="normal" if net_balance >= 0 else "inverse")
    if total_income > 0:
        col4.metric("Savings Rate", f"{(net_balance / total_income * 100):.1f}%")

# ---------------- Optimized Forecasting Tab ----------------
def render_forecasting():
    st.header("🔮 AI Expense Forecasting")
    
    if not st.session_state.token:
        st.info("🔐 Please login to access forecasting")
        return
    
    # Initialize cache for categories
    if 'forecast_categories' not in st.session_state:
        st.session_state.forecast_categories = ["all"]
    if 'categories_last_fetch' not in st.session_state:
        st.session_state.categories_last_fetch = 0
    
    # Get categories with caching
    current_time = time.time()
    if (not st.session_state.forecast_categories or 
        current_time - st.session_state.categories_last_fetch > 300):
        
        r = api_request("GET", "/forecast/categories", token=st.session_state.token)
        if r and r.status_code == 200:
            data = safe_json(r)
            if data and "categories" in data:
                st.session_state.forecast_categories = ["all"] + [cat for cat in data["categories"] if cat not in ["all", "Uncategorized"]]
                st.session_state.categories_last_fetch = current_time
    
    categories = st.session_state.forecast_categories
    
    col1, col2, col3 = st.columns(3)
    with col1:
        forecast_category = st.selectbox("📊 Forecast Category", categories, key="forecast_cat")
    with col2:
        months_ahead = st.slider("📅 Forecast Period (months)", 1, 12, 6, key="months_ahead")
    with col3:
        if st.button("🚀 Generate Forecast", use_container_width=True, key="gen_forecast"):
            with st.spinner("🤖 AI is generating forecast..."):
                payload = {"category": forecast_category, "months_ahead": months_ahead}
                r = api_request("POST", "/forecast", token=st.session_state.token, json=payload)
                
                if r and r.status_code == 200:
                    forecast_data = safe_json(r)
                    if forecast_data and forecast_data.get("success"):
                        st.session_state.forecast_result = forecast_data
                        st.success("✅ Forecast generated!")
                    else:
                        st.error("❌ Forecast failed")
                else:
                    st.error("❌ Service error")
    
    # Display results
    if "forecast_result" in st.session_state:
        forecast_data = st.session_state.forecast_result
        forecast = forecast_data.get("forecast", {})
        
        # Summary metrics
        st.subheader("📈 Forecast Summary")
        summary = forecast.get("summary", {})
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Avg Monthly", f"₹{summary.get('avg_monthly_forecast', 0):,.2f}")
        col2.metric("📊 Total Period", f"₹{summary.get('total_forecast_period', 0):,.2f}")
        col3.metric("📅 Forecast Days", summary.get('forecast_period_days', 0))
        
        # Chart
        historical_data = forecast.get("historical_data", [])
        forecast_data_list = forecast.get("forecast_data", [])
        
        if historical_data and forecast_data_list:
            dates, actuals, forecasts, lowers, uppers = [], [], [], [], []
            
            # Historical data
            for point in historical_data:
                dates.append(point['date'])
                actuals.append(point['actual'])
                forecasts.append(None)
                lowers.append(None)
                uppers.append(None)
            
            # Forecast data
            for point in forecast_data_list:
                dates.append(point['date'])
                actuals.append(None)
                forecasts.append(point['predicted'])
                lowers.append(point['predicted_lower'])
                uppers.append(point['predicted_upper'])
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates[:len(historical_data)], y=actuals[:len(historical_data)],
                mode='lines', name='Historical Expenses', line=dict(color='blue', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=dates[len(historical_data):], y=forecasts[len(historical_data):],
                mode='lines', name='Forecast', line=dict(color='red', width=2, dash='dash')
            ))
            fig.add_trace(go.Scatter(
                x=dates[len(historical_data):] + dates[len(historical_data):][::-1],
                y=uppers[len(historical_data):] + lowers[len(historical_data):][::-1],
                fill='toself', fillcolor='rgba(255,0,0,0.2)', line=dict(color='rgba(255,255,255,0)'),
                name='Confidence Interval', hoverinfo='skip'
            ))
            
            fig.update_layout(
                title="Expense Forecast: Historical vs Predicted",
                xaxis_title="Date",
                yaxis_title="Amount (₹)",
                hovermode='x unified',
                height=500,
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        with st.expander("📋 Forecast Data"):
            if forecast_data_list:
                st.dataframe(pd.DataFrame(forecast_data_list), use_container_width=True)

# ---------------- FIXED Goals Tab ----------------
def render_goals():
    st.header("🎯 Financial Goals")
    
    if not st.session_state.token:
        st.info("🔐 Please login to manage your goals")
        return
    
    # Two-column layout
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        render_goals_list()
    
    with col2:
        render_ai_coaching()

def render_goals_list():
    """Render the goals list and creation form"""
    st.subheader("📋 Your Goals")
    
    # Goal Creation Form
    with st.expander("➕ Create New Goal", expanded=False):
        with st.form("create_goal", clear_on_submit=True):
            goal_name = st.text_input("🎯 Goal Name", placeholder="e.g., New Laptop", key="goal_name")
            goal_type = st.selectbox("📊 Goal Type", ["savings", "spending_reduction", "category_budget"], key="goal_type")
            target_amount = st.number_input("💰 Target Amount (₹)", min_value=0.0, value=10000.0, step=1000.0, key="target_amount")
            target_date = st.date_input("📅 Target Date", min_value=date.today(), key="target_date")
            
            category = ""
            if goal_type in ["spending_reduction", "category_budget"]:
                category = st.selectbox("📁 Category", ["", "Groceries", "Entertainment", "Dining", "Shopping", "Transport", "Utilities"], key="goal_category")
            
            description = st.text_area("📝 Description", placeholder="Describe your goal...", key="goal_desc")
            
            submitted = st.form_submit_button("💾 Create Goal", use_container_width=True)
            if submitted:
                if goal_name and target_amount > 0:
                    payload = {
                        "goal_name": goal_name,
                        "goal_type": goal_type,
                        "target_amount": float(target_amount),
                        "target_date": target_date.isoformat(),
                        "category": category if category else None,
                        "description": description
                    }
                    
                    r = api_request("POST", "/goals", token=st.session_state.token, json=payload)
                    
                    if r and r.status_code == 201:
                        result = safe_json(r)
                        if result and result.get("success"):
                            st.success("✅ Goal created successfully!")
                            st.session_state.goals_data = None  # Force refresh
                        else:
                            st.error("❌ Failed to create goal in database")
                    else:
                        st.error(f"❌ Server error: {r.status_code if r else 'No response'}")
                else:
                    st.error("❌ Please fill in all required fields")
    
    # # Debug button to check goals
    # if st.button("🐛 Debug Goals", key="debug_goals"):
    #     r = api_request("GET", "/debug/goals", token=st.session_state.token)
    #     if r and r.status_code == 200:
    #         debug_data = safe_json(r)
    #         st.write("🔍 Debug Info:", debug_data)
    
    # Load goals
    if st.session_state.get('goals_data') is None:
        with st.spinner("🔄 Loading goals..."):
            r = api_request("GET", "/goals", token=st.session_state.token)
            
            if r and r.status_code == 200:
                goals_data = safe_json(r)
                if goals_data and goals_data.get("success"):
                    st.session_state.goals_data = goals_data.get("goals", [])
                    if st.session_state.goals_data:
                        st.success(f"✅ Loaded {len(st.session_state.goals_data)} goal(s)")
                else:
                    st.session_state.goals_data = []
                    st.error("❌ Failed to load goals from server")
            else:
                st.session_state.goals_data = []
                st.error(f"❌ Server error: {r.status_code if r else 'No response'}")
    
    goals = st.session_state.goals_data or []
    
    if goals:
        st.success(f"🎯 Found {len(goals)} goal(s)")
        for goal in goals:
            with st.container():
                # Goal header
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{goal['goal_name']}**")
                    if goal.get('description'):
                        st.caption(f"*{goal['description']}*")
                with col2:
                    progress = goal.get('progress_percent', 0)
                    st.write(f"**{progress:.1f}%**")
                
                # Progress bar
                st.progress(progress / 100)
                
                # Goal info and actions
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                with col1:
                    st.metric("Target", f"₹{goal['target_amount']:,.0f}")
                with col2:
                    st.metric("Due In", f"{goal['days_remaining']} days")
                with col3:
                    if st.button("🤖", key=f"coach_{goal['id']}", help="Get AI Coaching", use_container_width=True):
                        st.session_state.selected_goal_id = goal['id']
                        st.session_state.coaching_loading = True
                with col4:
                    if st.button("🗑️", key=f"delete_{goal['id']}", help="Delete Goal", use_container_width=True):
                        with st.spinner("Deleting..."):
                            r = api_request("DELETE", f"/goals/{goal['id']}", token=st.session_state.token)
                            if r and r.status_code == 200:
                                st.success("✅ Goal deleted!")
                                st.session_state.goals_data = None
                            else:
                                st.error("❌ Delete failed")
                
                # Add Savings Section
                with st.expander("💰 Add Savings", expanded=False):
                    if goal.get('status') == 'achieved' or goal['progress_percent'] >= 100:
                        st.success("🎉 Goal already achieved!")
                    else:
                        col_s1, col_s2 = st.columns([2, 1])
                        with col_s1:
                            savings_amount = st.number_input("Amount", min_value=0.0, step=100.0, key=f"save_{goal['id']}")
                            savings_note = st.text_input("Note", placeholder="e.g., Salary savings", key=f"note_{goal['id']}")
                        with col_s2:
                            if st.button("💾 Save", key=f"save_btn_{goal['id']}", use_container_width=True):
                                if savings_amount > 0:
                                    r = api_request("POST", f"/goals/{goal['id']}/savings", 
                                                  token=st.session_state.token,
                                                  json={"amount": savings_amount, "description": savings_note})
                                    if r and r.status_code == 200:
                                        result = safe_json(r)
                                        st.success(f"✅ {result.get('message', 'Savings added!')}")
                                        st.session_state.goals_data = None
                                    else:
                                        error_data = safe_json(r)
                                        st.error(f"❌ {error_data.get('error', 'Failed to add savings')}")
                
                if goal.get('category'):
                    st.caption(f"📁 Category: {goal['category']}")
                
                st.markdown("---")
    else:
        st.info("💡 No goals yet. Create your first goal above!")
    
    if st.button("🔄 Refresh Goals", use_container_width=True, key="refresh_goals"):
        st.session_state.goals_data = None
        st.success("Goals cache cleared - refreshing...")

def render_ai_coaching():
    """Render the AI Coaching panel"""
    st.subheader("🤖 AI Goal Coach")
    
    # Early return if no goal selected
    if not st.session_state.get('selected_goal_id'):
        st.info("👆 Select a goal and click the 🤖 button for AI coaching")
        return
    
    # Single button to trigger coaching analysis
    if st.button("🚀 Get AI Coaching", type="primary", use_container_width=True, key="get_coaching"):
        st.session_state.coaching_loading = True
    
    # Handle loading and display
    if st.session_state.get('coaching_loading'):
        load_and_display_coaching(st.session_state.selected_goal_id)
    
    # Reset button
    if st.session_state.get('coaching_data'):
        if st.button("🔄 New Analysis", use_container_width=True, key="new_analysis"):
            st.session_state.coaching_data = None
            st.session_state.coaching_loading = False

def load_and_display_coaching(goal_id):
    """Load coaching data and display it"""
    with st.spinner("🤖 AI Coach is analyzing..."):
        r = api_request("GET", f"/goals/{goal_id}/coaching", token=st.session_state.token)
        
        if r and r.status_code == 200:
            coaching_data = safe_json(r)
            if coaching_data and coaching_data.get("success"):
                st.session_state.coaching_data = coaching_data["coaching"]
                display_coaching_results(st.session_state.coaching_data)
            else:
                st.error("❌ Failed to get AI coaching")
        else:
            st.error("❌ Error connecting to AI coach")
        
        st.session_state.coaching_loading = False

def display_coaching_results(coaching):
    """Display the coaching analysis results"""
    if not coaching:
        return
    
    goal = coaching['goal']
    analysis = coaching['financial_analysis']
    action_plan = coaching['action_plan']
    savings_history = coaching.get('savings_history', [])
    
    # Coaching Header
    st.success(f"🎯 Coaching for: **{goal['goal_name']}**")
    
    # Success Probability
    prob = action_plan['success_probability']
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if prob >= 80:
            st.metric("🎯 Success Probability", f"{prob}%", "High", delta_color="normal")
        elif prob >= 60:
            st.metric("🎯 Success Probability", f"{prob}%", "Medium", delta_color="off")
        elif prob >= 40:
            st.metric("🎯 Success Probability", f"{prob}%", "Needs Work", delta_color="off")
        else:
            st.metric("🎯 Success Probability", f"{prob}%", "Challenging", delta_color="inverse")
    
    with col2:
        st.metric("📈 Feasibility", f"{analysis['feasibility_score']}%")
    
    with col3:
        st.metric("📅 Days Left", goal['days_remaining'])
    
    # Financial Analysis
    with st.expander("📊 Financial Analysis", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Monthly Income", f"₹{analysis.get('monthly_income', 0):,.0f}")
        with col2:
            st.metric("💸 Monthly Expenses", f"₹{analysis.get('monthly_expenses', 0):,.0f}")
        with col3:
            st.metric("🏦 Savings Capacity", f"₹{analysis.get('max_realistic_savings', 0):,.0f}")
        
        st.metric("🎯 Required Monthly", f"₹{action_plan.get('monthly_savings_needed', 0):,.0f}")
        
        if analysis.get('top_spending_categories'):
            st.write("**Top Spending Categories:**")
            for category in analysis['top_spending_categories'][:3]:
                st.write(f"• {category}")
    
    # Action Plan
    with st.expander("💡 AI Action Plan", expanded=True):
        if action_plan.get('action_steps'):
            for step in action_plan['action_steps']:
                st.write(step)
        
        if action_plan.get('recommendations'):
            st.write("### 💰 Optimization Opportunities:")
            for rec in action_plan['recommendations']:
                st.write(f"• **{rec.get('action')}**")
                st.write(f"  → {rec.get('impact')}")
    
    # Coaching Tips
    with st.expander("🎓 Coaching Tips"):
        if coaching.get('coaching_tips'):
            for tip in coaching['coaching_tips']:
                if "❌" in tip:
                    st.error(tip)
                elif "⚠️" in tip:
                    st.warning(tip)
                elif "✅" in tip or "🎉" in tip:
                    st.success(tip)
                else:
                    st.info(tip)
    
    # Savings History
    if savings_history:
        with st.expander("💰 Savings History"):
            total_saved = sum(s['amount'] for s in savings_history)
            st.metric("Total Saved", f"₹{total_saved:,.0f}")
            for saving in savings_history[:5]:
                st.write(f"📅 {saving['saved_date']}: ₹{saving['amount']:,.2f}")
                if saving['description']:
                    st.caption(f"Note: {saving['description']}")

# ---------------- Main App ----------------
def main():
    st.title("💰 BudgetWise AI - Expense Forecaster")
    st.markdown("**AI-Powered Expense Tracking & Automatic Categorization**")
    
    render_sidebar()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", "💳 Transactions", "📈 Reports", "🔮 Forecasting", "🎯 Goals"
    ])
    
    with tab1:
        render_dashboard()
    with tab2:
        render_transactions()
    with tab3:
        render_reports()
    with tab4:
        render_forecasting()
    with tab5:
        render_goals()

if __name__ == "__main__":
    main()