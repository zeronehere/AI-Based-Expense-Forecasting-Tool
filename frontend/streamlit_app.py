import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import io
import plotly.express as px

# ---------------- Page config ----------------
st.set_page_config(page_title="Expense Forecaster", layout="wide", page_icon="💸")

# ---------------- API base ----------------
API_BASE = "http://localhost:5000"  # Fixed backend URL

# ---------------- Helpers ----------------
def safe_rerun():
    """Safely force a UI reload"""
    try:
        st.rerun()
    except Exception:
        st.session_state["_reload_toggle"] = not st.session_state.get("_reload_toggle", False)

def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def api_request(method, path, token=None, json=None, files=None, timeout=20):
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
        else:
            return None
            
        return response
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")
        return None

# ---------------- User-Specific Data Management ----------------
def get_user_transactions():
    """Get transactions for current user from backend"""
    if not st.session_state.get("token"):
        return pd.DataFrame()
    
    cache_key = f"user_{st.session_state.user_email}_transactions"
    
    # Return cached data if available
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    # Fetch from backend
    r = api_request("GET", "/transactions", token=st.session_state.token)
    
    if isinstance(r, Exception) or not r or r.status_code != 200:
        st.error("❌ Failed to load your transactions")
        return pd.DataFrame()
    
    txs = safe_json(r) or []
    if not txs:
        df = pd.DataFrame(columns=['date', 'amount', 'description', 'category', 'type'])
    else:
        df = pd.DataFrame(txs)
        # Convert data types
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            df = df.dropna(subset=['date', 'amount'])
    
    # Cache the data
    st.session_state[cache_key] = df
    return df

def get_user_overview():
    """Get user overview from backend"""
    if not st.session_state.get("token"):
        return None
    
    cache_key = f"user_{st.session_state.user_email}_overview"
    
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    r = api_request("GET", "/reports/overview", token=st.session_state.token)
    
    if isinstance(r, Exception) or not r or r.status_code != 200:
        # Calculate locally if backend fails
        df = get_user_transactions()
        if df.empty:
            return {"total_income": 0, "total_expense": 0, "net_balance": 0, "recent_transactions": 0}
        
        total_income = df[df['type'] == 'income']['amount'].sum()
        total_expense = df[df['type'] == 'expense']['amount'].sum()
        net_balance = total_income - total_expense
        
        # Recent transactions (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_count = len(df[df['date'] >= thirty_days_ago])
        
        overview = {
            "total_income": float(total_income),
            "total_expense": float(total_expense),
            "net_balance": float(net_balance),
            "recent_transactions": int(recent_count)
        }
    else:
        overview = safe_json(r) or {}
    
    st.session_state[cache_key] = overview
    return overview

def get_user_category_report(days=30):
    """Get category report from backend"""
    if not st.session_state.get("token"):
        return None
    
    cache_key = f"user_{st.session_state.user_email}_category_{days}"
    
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    r = api_request("GET", f"/reports/category?days={days}", token=st.session_state.token)
    
    if isinstance(r, Exception) or not r or r.status_code != 200:
        # Calculate locally if backend fails
        df = get_user_transactions()
        if df.empty:
            return {"total_expense": 0, "by_category": []}
        
        start_date = datetime.now() - timedelta(days=days)
        expense_df = df[(df['date'] >= start_date) & (df['type'] == 'expense')]
        
        if expense_df.empty:
            return {"total_expense": 0, "by_category": []}
        
        category_totals = expense_df.groupby('category')['amount'].sum().reset_index()
        category_totals = category_totals.rename(columns={'amount': 'total'})
        total_expense = category_totals['total'].sum()
        
        # Add percentages
        category_totals['percent'] = (category_totals['total'] / total_expense * 100).round(2)
        
        report = {
            "total_expense": float(total_expense),
            "by_category": category_totals.to_dict('records')
        }
    else:
        report = safe_json(r) or {}
    
    st.session_state[cache_key] = report
    return report

def clear_user_cache():
    """Clear all cached data for current user"""
    if st.session_state.get("user_email"):
        user_prefix = f"user_{st.session_state.user_email}_"
        cache_keys = [key for key in st.session_state.keys() if key.startswith(user_prefix)]
        for key in cache_keys:
            if key in st.session_state:
                del st.session_state[key]

# ---------------- Authentication ----------------
def handle_auth(email, password, is_register=False):
    """Handle user authentication"""
    endpoint = "/auth/register" if is_register else "/auth/login"
    r = api_request("POST", endpoint, json={"email": email, "password": password})
    
    if isinstance(r, Exception) or not r or r.status_code not in [200, 201]:
        st.error("❌ Authentication failed. Check your credentials.")
        return False
    
    payload = safe_json(r) or {}
    token = payload.get("access_token")
    if token:
        st.session_state.token = token
        st.session_state.user_email = payload.get("email", email)
        st.success("✅ Login successful!")
        return True
    
    return False

# ---------------- Session State Management ----------------
def init_session_state():
    """Initialize session state"""
    if "token" not in st.session_state:
        st.session_state.token = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "last_added_tx" not in st.session_state:
        st.session_state.last_added_tx = None

init_session_state()

# ---------------- CSS ----------------
st.markdown("""
    <style>
    .block-container { padding: 1rem 1rem; }
    .stButton>button { height: 44px; font-size: 15px; }
    .metric-container { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .ai-categorized { background-color: #e6f3ff !important; }
    .success-box { background-color: #d4edda; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745; }
    </style>
""", unsafe_allow_html=True)

# ---------------- Authentication Sidebar ----------------
def render_sidebar():
    """Render sidebar with authentication and quick insights"""
    with st.sidebar:
        st.title("🔐 Account")
        
        if st.session_state.token:
            st.success(f"Logged in as **{st.session_state.user_email}**")
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
                clear_user_cache()
                st.session_state.token = None
                st.session_state.user_email = None
                st.session_state.last_added_tx = None
                st.success("✅ Logged out successfully!")
                st.rerun()
        else:
            auth_tab = st.radio("Action", ["Login", "Register"], horizontal=True, key="auth_tab")
            email = st.text_input("📧 Email", key="auth_email")
            password = st.text_input("🔒 Password", type="password", key="auth_pwd")
            
            if st.button("Submit", use_container_width=True, key="auth_submit"):
                if not email or not password:
                    st.warning("Please enter both email and password.")
                else:
                    is_register = (auth_tab == "Register")
                    if handle_auth(email, password, is_register):
                        st.rerun()

        st.markdown("---")
        
        st.header("📊 Quick Insights")
        if st.session_state.token:
            overview = get_user_overview()
            
            if overview:
                total_income = overview.get("total_income", 0)
                total_expense = overview.get("total_expense", 0)
                recent_count = overview.get("recent_transactions", 0)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("💰 Expenses", f"₹{total_expense:,.2f}")
                with col2:
                    st.metric("💵 Income", f"₹{total_income:,.2f}")
                
                st.markdown("**Recent Activity**")
                st.caption(f"📈 {recent_count} transactions in last 30 days")
                
                if total_income == 0 and total_expense == 0:
                    st.info("💡 Add your first transaction to see insights!")
            else:
                st.metric("Total Expense", "₹0.00")
                st.metric("Total Income", "₹0.00")
                st.info("No transactions yet. Add your first transaction!")

# ---------------- Transactions Tab ----------------
def render_transactions():
    """Render transactions management tab"""
    st.header("💳 Your Transaction Management")
    
    if not st.session_state.token:
        st.info("🔐 Please login to manage your transactions")
        return

    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.expander("➕ Add Transaction", expanded=True):
            if st.session_state.last_added_tx:
                tx_info = st.session_state.last_added_tx
                st.success(
                    f"✅ **Transaction Added Successfully!**\n\n"
                    f"**Description:** {tx_info['description']}\n"
                    f"**Amount:** ₹{tx_info['amount']:,.2f}\n"
                    f"**Category:** {tx_info['category']}"
                )
                st.session_state.last_added_tx = None
            
            with st.form("manual_add", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    t_date = st.date_input("📅 Date", value=date.today(), key="tx_date")
                    t_amount = st.number_input("💰 Amount", value=0.0, format="%.2f", step=100.0, key="tx_amount")
                with col_b:
                    t_type = st.selectbox("🔸 Type", ("expense", "income"), key="tx_type")
                    t_desc = st.text_input("📝 Description", 
                                         placeholder="e.g., Netflix subscription, Uber ride, Grocery shopping",
                                         key="transaction_desc")
                
                categories = ["", "Groceries", "Transport", "Dining", "Rent", "Utilities", "Entertainment", 
                             "Healthcare", "Education", "Shopping", "Travel", "Miscellaneous"]
                
                t_cat = st.selectbox(
                    "Choose category (AI will auto-categorize if left empty):",
                    categories,
                    help="Leave empty for AI auto-categorization based on description",
                    key="category_dropdown"
                )
                
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
                        
                        if isinstance(r, Exception) or not r or r.status_code not in [200, 201]:
                            st.error("❌ Failed to add transaction")
                        else:
                            response_data = safe_json(r) or {}
                            final_category = response_data.get("category", "Uncategorized")
                            
                            st.session_state.last_added_tx = {
                                "description": t_desc,
                                "amount": float(t_amount),
                                "category": final_category
                            }
                            
                            clear_user_cache()
                            st.rerun()

    with col2:
        with st.expander("📁 Bulk Upload"):
            uploaded = st.file_uploader("Choose CSV file", type=["csv"], 
                                      help="Upload your transactions in CSV format", 
                                      key="csv_uploader")
            if uploaded:
                try:
                    preview = pd.read_csv(uploaded)
                    st.success(f"📊 File loaded: {len(preview)} rows detected")
                    st.info("💡 Your CSV transactions will be automatically categorized by AI based on descriptions")
                    
                    if st.button("🚀 Upload to Your Account", use_container_width=True, key="upload_btn"):
                        with st.spinner("Processing your CSV with AI categorization..."):
                            file_bytes = uploaded.getvalue()
                            files = {'file': (uploaded.name, file_bytes)}
                            r = api_request("POST", "/transactions/bulk", 
                                          token=st.session_state.token, files=files, timeout=120)
                            
                            if isinstance(r, Exception) or not r or r.status_code != 200:
                                st.error("❌ Failed to upload CSV")
                            else:
                                result = safe_json(r) or {}
                                inserted = result.get("inserted", 0)
                                st.success(f"✅ Your CSV uploaded successfully! {inserted} transactions processed with AI categorization")
                                clear_user_cache()
                                st.rerun()
                except Exception as e:
                    st.error(f"❌ Error reading your CSV: {e}")

    st.subheader("📋 Your Transactions")
    
    df = get_user_transactions()
    
    if not df.empty:
        auto_categorized = len(df[df['category'].notna() & 
                                (df['category'] != '') & 
                                (df['category'] != 'Uncategorized')])
        total_tx = len(df)
        
        if total_tx > 0:
            st.info(f"🤖 {auto_categorized}/{total_tx} of your transactions categorized by AI")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            preset = st.selectbox("⏰ Time Period", 
                                ["Last 30 days", "Last 90 days", "This month", "This year", "All time"],
                                key="time_period")
        with col2:
            search_term = st.text_input("🔍 Search your descriptions", key="search_desc")
        with col3:
            sort_by = st.selectbox("📊 Sort by", 
                                 ["Date (newest)", "Date (oldest)", "Amount (high)", "Amount (low)"],
                                 key="sort_by")
        
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
            if not df.empty:
                start_date = df['date'].min().date()
                end_date = df['date'].max().date()
            else:
                start_date = today - timedelta(days=365)
                end_date = today
        
        mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
        filtered_df = df.loc[mask]
        
        st.caption(f"📊 Found {len(filtered_df)} of your transactions in selected period")
        
        if search_term:
            filtered_df = filtered_df[filtered_df['description'].str.contains(search_term, case=False, na=False)]
        
        sort_options = {
            "Date (newest)": ('date', False),
            "Date (oldest)": ('date', True),
            "Amount (high)": ('amount', False),
            "Amount (low)": ('amount', True)
        }
        sort_col, sort_asc = sort_options[sort_by]
        filtered_df = filtered_df.sort_values(sort_col, ascending=sort_asc)
        
        display_count = min(50, len(filtered_df))
        display_df = filtered_df.head(display_count).copy()
        
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        display_df['amount'] = display_df['amount'].map(lambda x: f"₹{x:,.2f}")
        
        display_columns = {
            'date': 'Date', 
            'description': 'Description', 
            'amount': 'Amount', 
            'category': 'Category', 
            'type': 'Type'
        }
        
        styled_df = display_df[list(display_columns.keys())].rename(columns=display_columns)
        
        # CHANGED: Black background for AI-categorized rows
        def highlight_ai_categorized(row):
            if row['Category'] and row['Category'] != 'Uncategorized':
                return ['background-color: #000000; color: #ffffff'] * len(row)  # Black bg, white text
            return [''] * len(row)
        
        try:
            final_styled_df = styled_df.style.apply(highlight_ai_categorized, axis=1)
            st.dataframe(final_styled_df, use_container_width=True, hide_index=True)
        except Exception:
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.caption(f"Showing {display_count} of {len(filtered_df)} of your transactions • ⚫ Black rows = AI categorized")
        
        if st.button("🔄 Refresh Your Data", use_container_width=True, key="refresh_btn"):
            clear_user_cache()
            st.rerun()
    else:
        st.info("💳 No transactions found in your account. Add your first transaction above!")

# ---------------- Dashboard Tab ----------------
def render_dashboard():
    """Render the main dashboard tab"""
    st.header("📊 Your Dashboard Overview")
    
    if not st.session_state.token:
        st.info("🔐 Please login to view your dashboard")
        return
        
    # Get user data
    df = get_user_transactions()
    
    if df.empty:
        st.info("💳 No transactions found in your account. Add your first transaction to see insights!")
        return
        
    st.subheader("💰 Your Financial Summary")
    
    # Get overview
    overview = get_user_overview()
    
    if overview:
        total_income = overview.get("total_income", 0)
        total_expense = overview.get("total_expense", 0)
        net_balance = overview.get("net_balance", 0)
        recent_count = overview.get("recent_transactions", 0)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Your Income", f"₹{total_income:,.2f}")
        with col2:
            st.metric("Your Expenses", f"₹{total_expense:,.2f}", delta_color="inverse")
        with col3:
            st.metric("Your Net Balance", f"₹{net_balance:,.2f}", 
                     delta_color="normal" if net_balance >= 0 else "inverse")
        with col4:
            st.metric("Recent Tx", f"{recent_count}")

    st.subheader("🕒 Your Recent Transactions")
    recent_tx = df.sort_values('date', ascending=False).head(8)
    if not recent_tx.empty:
        display_recent = recent_tx[['date', 'description', 'amount', 'category']].copy()
        display_recent['date'] = display_recent['date'].dt.strftime('%Y-%m-%d')
        display_recent['amount'] = display_recent['amount'].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(
            display_recent.rename(columns={
                'date': 'Date', 'description': 'Description', 
                'amount': 'Amount', 'category': 'Category'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent transactions in your account")

    st.subheader("📈 Your Spending by Category (AI Categorized)")
    
    # Get category report
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

# ---------------- Reports Tab ----------------
def render_reports():
    """Render reports and analytics tab"""
    st.header("📈 Your Spending Reports & Analytics")
    
    if not st.session_state.token:
        st.info("🔐 Please login to view your reports")
        return
        
    # Get user transactions
    df = get_user_transactions()
    
    if df.empty:
        st.info("📊 No transaction data in your account for reporting")
        return
        
    # Report Period Selection
    col1, col2 = st.columns(2)
    with col1:
        report_preset = st.selectbox("📅 Report Period", 
                                   ["Last 3 months", "Last 6 months", "This year", "All time"],
                                   key="report_period")
    
    # Date range calculation
    today = date.today()
    
    if report_preset == "Last 3 months":
        days_back = 90
    elif report_preset == "Last 6 months":
        days_back = 180
    elif report_preset == "This year":
        days_back = (today - today.replace(month=1, day=1)).days
    else:  # "All time"
        if not df.empty:
            days_back = (df['date'].max().date() - df['date'].min().date()).days
        else:
            days_back = 365
    
    start_date = today - timedelta(days=days_back)
    end_date = today
    
    # Display the date range being used
    st.caption(f"📅 Showing your data from {start_date} to {end_date}")
    
    # Filter data for report period
    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
    report_df = df.loc[mask]
    
    st.caption(f"📊 Found {len(report_df)} of your transactions in selected period")
    
    if report_df.empty:
        st.info("No transactions found in your account for the selected period")
        return
    
    # Monthly Spending Summary
    st.subheader("📅 Your Monthly Spending Summary")
    
    if not report_df.empty:
        # Generate monthly summary
        report_df['month'] = report_df['date'].dt.to_period('M')
        monthly_summary = report_df.groupby(['month', 'type'])['amount'].sum().unstack(fill_value=0)
        
        # Ensure we have both income and expense columns
        if 'income' not in monthly_summary.columns:
            monthly_summary['income'] = 0
        if 'expense' not in monthly_summary.columns:
            monthly_summary['expense'] = 0
        
        # Calculate net
        monthly_summary['net'] = monthly_summary['income'] - monthly_summary['expense']
        monthly_summary = monthly_summary.reset_index()
        monthly_summary['month'] = monthly_summary['month'].astype(str)
        
        st.caption(f"Monthly summary generated for {len(monthly_summary)} months of your data")
        
        # Create the trend chart
        fig_trend = px.line(
            monthly_summary, 
            x='month', 
            y=['income', 'expense'],
            title="Your Monthly Income vs Expenses Trend",
            labels={'value': 'Amount (₹)', 'variable': 'Type', 'month': 'Month'}
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # Monthly summary table
        display_monthly = monthly_summary.copy()
        display_monthly['income'] = display_monthly['income'].map(lambda x: f"₹{x:,.2f}")
        display_monthly['expense'] = display_monthly['expense'].map(lambda x: f"₹{x:,.2f}")
        display_monthly['net'] = display_monthly['net'].map(lambda x: f"₹{x:,.2f}")
        
        st.dataframe(
            display_monthly.rename(columns={
                'month': 'Month', 'income': 'Income', 'expense': 'Expenses', 'net': 'Net'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No monthly data in your account for the selected period")
    
    # Category-wise Spending Report
    st.subheader("📊 Your AI-Categorized Spending Report")
    
    # Get category report
    category_data = get_user_category_report(days=days_back)
    
    if category_data and category_data.get("by_category"):
        by_category = category_data["by_category"]
        total_expense = category_data.get("total_expense", 0)
        
        if total_expense > 0:
            cat_df = pd.DataFrame(by_category)
            cat_df = cat_df.sort_values('total', ascending=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_bar = px.bar(
                    cat_df, 
                    x='total', 
                    y='category', 
                    orientation='h',
                    title="Your AI-Categorized Spending",
                    labels={'total': 'Amount (₹)', 'category': 'Category'}
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                st.write("**Your Category Breakdown**")
                breakdown = cat_df.sort_values('total', ascending=False).copy()
                breakdown['percentage'] = (breakdown['total'] / total_expense * 100).round(1)
                breakdown['total'] = breakdown['total'].map(lambda x: f"₹{x:,.2f}")
                
                st.dataframe(
                    breakdown.rename(columns={'category': 'Category', 'total': 'Amount', 'percentage': '%'}),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("No expense data in your account for the selected period")
    else:
        st.info("No categorized expense data in your account for the selected period")
    
    # Income vs Expense Summary
    st.subheader("💰 Your Income vs Expense Summary")
    
    total_income_period = report_df[report_df['type']=='income']['amount'].sum()
    total_expense_period = report_df[report_df['type']=='expense']['amount'].sum()
    net_balance_period = total_income_period - total_expense_period
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Your Income", f"₹{total_income_period:,.2f}")
    with col2:
        st.metric("Your Expenses", f"₹{total_expense_period:,.2f}")
    with col3:
        st.metric("Your Net Balance", f"₹{net_balance_period:,.2f}", 
                 delta_color="normal" if net_balance_period >= 0 else "inverse")
    with col4:
        if total_income_period > 0:
            savings_rate = (net_balance_period / total_income_period * 100)
            st.metric("Your Savings Rate", f"{savings_rate:.1f}%")

# ---------------- Main App ----------------
def main():
    """Main application function"""
    st.title("💰 BudgetWise AI - Expense Forecaster")
    st.markdown("**AI-Powered Expense Tracking & Automatic Categorization**")
    
    st.info("🎯 **MILESTONE 1 & 2 COMPLETE**: User Authentication + AI Transaction Categorization!")
    
    render_sidebar()
    
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💳 Transactions", "📈 Reports"])
    
    with tab1:
        render_dashboard()
    
    with tab2:
        render_transactions()
    
    with tab3:
        render_reports()

if __name__ == "__main__":
    main()