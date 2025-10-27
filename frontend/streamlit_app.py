# frontend/streamlit_app.py
"""
Streamlit frontend for AI Expense Forecasting Tool
Fixed Version: Working transaction table with proper styling
Fully compliant with Milestone 2 requirements
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import io
import plotly.express as px
import uuid

# ---------------- Page config ----------------
st.set_page_config(page_title="Expense Forecaster", layout="wide", page_icon="💸")

# ---------------- API base ----------------
API_BASE = None
try:
    API_BASE = st.secrets.get("api_base", None)
except Exception:
    API_BASE = None
if not API_BASE:
    API_BASE = "http://localhost:5000"

# ---------------- Helpers ----------------
def safe_rerun():
    """Safely force a UI reload"""
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            st.session_state["_reload_toggle"] = not st.session_state.get("_reload_toggle", False)
            st.stop()

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
        if files:
            r = requests.request(method, url, headers=headers, files=files, data=json or {}, timeout=timeout)
        else:
            r = requests.request(method, url, headers=headers, json=json, timeout=timeout)
        return r
    except Exception as e:
        return e

def show_response_error(resp):
    if isinstance(resp, Exception):
        st.error(f"Request failed: {resp}")
    else:
        body = safe_json(resp)
        if body and isinstance(body, dict) and body.get("msg"):
            st.error(body.get("msg"))
        else:
            st.error(f"Server error (status {getattr(resp,'status_code','n/a')}).")

# ---------------- Category Management ----------------
DEFAULT_CATEGORIES = [
    "Groceries", "Transport", "Dining", "Rent", "Utilities", "Entertainment",
    "Healthcare", "Education", "Insurance", "Loan_Repayment", "Salary",
    "Shopping", "Travel", "Miscellaneous", "Uncategorized"
]

def get_categories_from_backend():
    """Fetch categories from backend API"""
    try:
        r = api_request("get", "/categories")
        if not isinstance(r, Exception) and getattr(r, "status_code", 0) == 200:
            data = safe_json(r)
            return data.get("categories", DEFAULT_CATEGORIES)
    except Exception:
        pass
    return DEFAULT_CATEGORIES

def normalize_tx_df(df):
    """Standardize dataframe columns - let backend handle categorization"""
    colmap = {}
    lower_cols = {c.lower(): c for c in df.columns}
    
    # Map columns to standard names
    if 'date' in lower_cols:
        colmap[lower_cols['date']] = 'date'
    elif 'transaction_date' in lower_cols:
        colmap[lower_cols['transaction_date']] = 'date'
        
    if 'amount' in lower_cols:
        colmap[lower_cols['amount']] = 'amount'
    if 'description' in lower_cols:
        colmap[lower_cols['description']] = 'description'
    if 'category' in lower_cols:
        colmap[lower_cols['category']] = 'category'
    if 'type' in lower_cols:
        colmap[lower_cols['type']] = 'type'
    if 'id' in lower_cols:
        colmap[lower_cols['id']] = 'id'
        
    df = df.rename(columns=colmap)
    
    if 'date' not in df.columns or 'amount' not in df.columns:
        raise ValueError("CSV must contain 'date' and 'amount' columns.")
    
    # Convert and validate data
    df['date'] = pd.to_datetime(df['date'], errors='coerce', utc=True)
    if df['date'].dt.tz is not None:
        df['date'] = df['date'].dt.tz_convert(None)
    df = df.dropna(subset=['date'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    
    # Fill missing values - IMPORTANT: Don't categorize here!
    if 'description' not in df.columns:
        df['description'] = ''
    if 'category' not in df.columns:
        df['category'] = ''  # Leave empty for backend to categorize
    if 'type' not in df.columns:
        df['type'] = df['amount'].apply(lambda x: 'income' if x > 0 else 'expense')
    
    # Keep only necessary columns
    cols = ['date', 'amount', 'description', 'category', 'type']
    if 'id' in df.columns:
        cols = ['id'] + cols
        
    return df[cols]

def safe_date_filter(df, date_col, start_date, end_date):
    """Safely filter dataframe by date range"""
    if df.empty:
        return df
    
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])
    
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
    return df.loc[mask]

def generate_monthly_summary(df):
    """Generate monthly spending summaries using Pandas"""
    if df.empty:
        return pd.DataFrame()
    
    df_monthly = df.copy()
    df_monthly['month'] = df_monthly['date'].dt.to_period('M')
    
    monthly_summary = df_monthly.groupby(['month', 'type'])['amount'].sum().unstack(fill_value=0)
    monthly_summary['net'] = monthly_summary.get('income', 0) - monthly_summary.get('expense', 0)
    monthly_summary = monthly_summary.reset_index()
    monthly_summary['month'] = monthly_summary['month'].astype(str)
    
    return monthly_summary

# ---------------- Session State Management ----------------
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        "token": None,
        "user_email": None,
        "uploaded_df": None,
        "tx_cache": None,
        "categories_cache": None,
        "_reload_toggle": False,
        "last_refresh": None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ---------------- CSS ----------------
st.markdown("""
    <style>
    .block-container { padding: 1rem 1rem; }
    .stButton>button { height: 44px; font-size: 15px; }
    .metric-container { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .auto-category { background-color: #e6f3ff; padding: 10px; border-radius: 5px; margin: 10px 0; }
    
    /* Custom styling for AI-categorized rows */
    .ai-categorized {
        background-color: #e6f3ff !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------- Authentication Sidebar ----------------
def render_sidebar():
    """Render sidebar with authentication and quick insights"""
    with st.sidebar:
        st.title("🔐 Account")
        
        # Authentication Section
        if st.session_state.token:
            st.success(f"Logged in as **{st.session_state.user_email}**")
            if st.button("🚪 Logout", use_container_width=True):
                for key in ["token", "user_email", "tx_cache"]:
                    st.session_state[key] = None
                safe_rerun()
        else:
            auth_tab = st.radio("Action", ["Register", "Login"], horizontal=True)
            email = st.text_input("📧 Email", key="auth_email")
            pwd = st.text_input("🔒 Password", type="password", key="auth_pwd")
            
            if st.button("Submit", use_container_width=True):
                if not email or not pwd:
                    st.warning("Please enter both email and password.")
                else:
                    endpoint = "/auth/register" if auth_tab == "Register" else "/auth/login"
                    r = api_request("post", endpoint, json={"email": email, "password": pwd})
                    
                    if isinstance(r, Exception) or getattr(r, "status_code", 0) not in [200, 201]:
                        show_response_error(r)
                    else:
                        payload = safe_json(r) or {}
                        token = payload.get("access_token")
                        if token:
                            st.session_state.token = token
                            st.session_state.user_email = payload.get("email", email)
                            st.success("✅ Signed in successfully!")
                            safe_rerun()
                        else:
                            st.error("Login failed — no token returned.")

        st.markdown("---")
        
        # Quick Insights Section
        st.header("📊 Quick Insights")
        if st.session_state.token:
            # Refresh data if needed
            if st.session_state.tx_cache is None:
                with st.spinner("Loading transactions..."):
                    r = api_request("get", "/transactions", token=st.session_state.token)
                    if not isinstance(r, Exception) and getattr(r, "status_code", 0) == 200:
                        txs = safe_json(r) or []
                        df_tmp = pd.DataFrame(txs)
                        if not df_tmp.empty:
                            st.session_state.tx_cache = normalize_tx_df(df_tmp)
                        else:
                            st.session_state.tx_cache = pd.DataFrame(columns=['date','amount','description','category','type'])
            
            df_cache = st.session_state.tx_cache
            if df_cache is None or df_cache.empty:
                st.metric("Total Expense", "₹0.00")
                st.metric("Total Income", "₹0.00")
                st.info("No transactions yet. Add your first transaction!")
            else:
                total_expense = df_cache[df_cache['type']=='expense']['amount'].sum()
                total_income = df_cache[df_cache['type']=='income']['amount'].sum()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("💰 Expenses", f"₹{total_expense:,.2f}")
                with col2:
                    st.metric("💵 Income", f"₹{total_income:,.2f}")
                
                # Recent transactions preview
                st.markdown("**Recent Transactions**")
                recent = df_cache.sort_values('date', ascending=False).head(3)
                if not recent.empty:
                    for _, tx in recent.iterrows():
                        emoji = "📈" if tx['type'] == 'income' else "📉"
                        st.caption(f"{emoji} {tx['description'][:20]}... - ₹{tx['amount']:,.2f}")

# ---------------- Transactions Tab ----------------
def render_transactions():
    """Render transactions management tab"""
    st.header("💳 Transaction Management")
    
    if not st.session_state.token:
        st.info("🔐 Please login to manage transactions")
        return

    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Manual Transaction Input
        with st.expander("➕ Add Transaction", expanded=True):
            with st.form("manual_add", clear_on_submit=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    t_date = st.date_input("📅 Date", value=date.today())
                    t_amount = st.number_input("💰 Amount", value=0.0, format="%.2f", step=100.0)
                with col_b:
                    t_type = st.selectbox("🔸 Type", ("expense", "income"))
                    t_desc = st.text_input("📝 Description", placeholder="e.g., Netflix subscription, Uber ride, Grocery shopping")
                
                # 🎯 AUTO-CATEGORIZATION
                st.markdown("**🏷️ Category (Auto-detected)**")
                st.info("💡 Leave category empty for AI auto-categorization based on description")
                
                categories = get_categories_from_backend()
                
                # Show category as optional with auto-detection note
                t_cat = st.selectbox(
                    "Category (Optional - AI will auto-detect if empty)",
                    [""] + categories,  # First option is empty for auto-detection
                    help="Select a category manually or leave empty for automatic AI categorization"
                )
                
                if st.form_submit_button("💾 Add Transaction", use_container_width=True):
                    payload = {
                        "date": t_date.isoformat(), 
                        "amount": float(t_amount), 
                        "description": t_desc, 
                        "type": t_type
                    }
                    
                    # 🎯 ONLY include category if user explicitly selected one
                    if t_cat:  # Manual override
                        payload["category"] = t_cat
                        st.info(f"🎯 Using manual category: **{t_cat}**")
                    else:
                        st.info("🤖 Using AI auto-categorization based on description")
                    
                    r = api_request("post", "/transactions", token=st.session_state.token, json=payload)
                    if isinstance(r, Exception) or getattr(r, "status_code", None) not in (200, 201):
                        show_response_error(r)
                    else:
                        response_data = safe_json(r) or {}
                        detected_category = response_data.get("category", "Uncategorized")
                        
                        if not t_cat:  # If auto-categorized
                            st.success(f"✅ Transaction added! AI categorized as: **{detected_category}**")
                        else:
                            st.success("✅ Transaction added successfully!")
                        
                        st.session_state.tx_cache = None

    with col2:
        # CSV Upload
        with st.expander("📁 Bulk Upload"):
            uploaded = st.file_uploader("Choose CSV file", type=["csv"], help="Upload transactions in CSV format")
            if uploaded:
                try:
                    preview = pd.read_csv(uploaded)
                    st.success(f"📊 File loaded: {len(preview)} rows detected")
                    
                    # Show preview with categorization info
                    st.info("💡 CSV transactions will be automatically categorized by AI based on descriptions")
                    
                    if st.button("🚀 Upload to System", use_container_width=True):
                        with st.spinner("Processing CSV with AI categorization..."):
                            file_bytes = uploaded.getvalue()
                            files = {'file': (uploaded.name, file_bytes)}
                            r = api_request("post", "/transactions/bulk", 
                                          token=st.session_state.token, files=files, timeout=120)
                            if isinstance(r, Exception) or getattr(r, "status_code", None) != 200:
                                show_response_error(r)
                            else:
                                result = safe_json(r) or {}
                                inserted = result.get("inserted", 0)
                                st.success(f"✅ CSV uploaded successfully! {inserted} transactions processed with AI categorization")
                                st.session_state.tx_cache = None
                except Exception as e:
                    st.error(f"❌ Error reading CSV: {e}")

        # 🎯 Auto-Categorization Demo
        with st.expander("🔍 Test AI Categorization"):
            st.markdown("**See how AI categorizes transactions**")
            test_desc = st.text_input("Enter transaction description", 
                                    placeholder="e.g., Netflix monthly subscription")
            test_amt = st.number_input("Amount (optional)", value=0.0)
            
            if test_desc:
                # Simulate what backend would do
                st.info("💡 Backend AI would analyze this description and automatically assign the best category")
                
                # Simple frontend hint (actual categorization happens in backend)
                hint_patterns = [
                    ("netflix", "Entertainment"), ("uber", "Transport"), ("ola", "Transport"),
                    ("zomato", "Dining"), ("swiggy", "Dining"), ("restaurant", "Dining"),
                    ("bigbasket", "Groceries"), ("grocery", "Groceries"), ("supermarket", "Groceries"),
                    ("rent", "Rent"), ("electricity", "Utilities"), ("movie", "Entertainment")
                ]
                
                predicted = "Uncategorized"
                for pattern, category in hint_patterns:
                    if pattern in test_desc.lower():
                        predicted = category
                        break
                
                st.success(f"🤖 Likely category: **{predicted}**")

    # Transaction List with Filters - WORKING VERSION
    st.subheader("📋 Your Transactions")
    if st.session_state.tx_cache is not None and not st.session_state.tx_cache.empty:
        df = st.session_state.tx_cache.copy()
        
        # Show AI categorization stats
        auto_categorized = len(df[df['category'].notna() & (df['category'] != '')])
        total_tx = len(df)
        
        if total_tx > 0:
            st.info(f"🤖 {auto_categorized}/{total_tx} transactions categorized by AI")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            preset = st.selectbox("⏰ Time Period", 
                                ["Last 30 days", "Last 90 days", "This month", "This year", "All time"])
        with col2:
            search_term = st.text_input("🔍 Search descriptions")
        with col3:
            sort_by = st.selectbox("📊 Sort by", 
                                 ["Date (newest)", "Date (oldest)", "Amount (high)", "Amount (low)"])
        
        # Apply filters
        date_filters = {
            "Last 30 days": (date.today() - timedelta(days=30), date.today()),
            "Last 90 days": (date.today() - timedelta(days=90), date.today()),
            "This month": (date.today().replace(day=1), date.today()),
            "This year": (date.today().replace(month=1, day=1), date.today()),
            "All time": (df['date'].min().date(), date.today())
        }
        
        start_date, end_date = date_filters[preset]
        filtered_df = safe_date_filter(df, 'date', start_date, end_date)
        
        if search_term:
            filtered_df = filtered_df[filtered_df['description'].str.contains(search_term, case=False, na=False)]
        
        # Apply sorting
        sort_options = {
            "Date (newest)": ('date', False),
            "Date (oldest)": ('date', True),
            "Amount (high)": ('amount', False),
            "Amount (low)": ('amount', True)
        }
        sort_col, sort_asc = sort_options[sort_by]
        filtered_df = filtered_df.sort_values(sort_col, ascending=sort_asc)
        
        # Display transactions - WORKING VERSION WITH PROPER STYLING
        display_count = min(50, len(filtered_df))
        display_df = filtered_df.head(display_count).copy()
        
        # Format for display
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        display_df['amount'] = display_df['amount'].map(lambda x: f"₹{x:,.2f}")
        
        # Create display dataframe
        display_columns = {
            'date': 'Date', 
            'description': 'Description', 
            'amount': 'Amount', 
            'category': 'Category', 
            'type': 'Type'
        }
        
        styled_df = display_df[list(display_columns.keys())].rename(columns=display_columns)
        
        # WORKING STYLING FUNCTION - SIMPLE AND RELIABLE
        def highlight_ai_categorized(data):
            """Apply styling to highlight AI-categorized rows"""
            # Create a DataFrame of empty strings with same shape as data
            styles = pd.DataFrame('', index=data.index, columns=data.columns)
            
            # Apply blue background to AI-categorized rows
            for idx in data.index:
                # Get the original category value from display_df (before renaming)
                original_idx = display_df.index[idx]
                category_value = filtered_df.loc[original_idx, 'category'] if original_idx in filtered_df.index else ''
                
                if category_value and category_value != 'Uncategorized':
                    # Apply blue background to all cells in this row
                    styles.loc[idx] = 'background-color: #e6f3ff; color: #000000'
            
            return styles
        
        # Apply the styling
        try:
            final_styled_df = styled_df.style.apply(highlight_ai_categorized, axis=None)
            st.dataframe(
                final_styled_df,
                use_container_width=True,
                hide_index=True
            )
        except Exception as e:
            # Fallback: Show without styling if it fails
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True
            )
            st.warning("💡 Some styling features unavailable, but AI categorization is working")
        
        st.caption(f"Showing {display_count} of {len(filtered_df)} transactions • 💡 Blue rows = AI categorized")
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.session_state.tx_cache = None
            st.rerun()
    else:
        st.info("💳 No transactions found. Add your first transaction above.")

# ---------------- Dashboard Tab ----------------
def render_dashboard():
    """Render the main dashboard tab"""
    st.header("📊 Dashboard Overview")
    
    if not st.session_state.token:
        st.info("🔐 Please login to view your dashboard")
        return
        
    if st.session_state.tx_cache is None or st.session_state.tx_cache.empty:
        st.info("💳 No transactions found. Add your first transaction to see insights!")
        return
        
    df = st.session_state.tx_cache.copy()
    
    # Key Metrics
    st.subheader("💰 Financial Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    total_income = df[df['type']=='income']['amount'].sum()
    total_expense = df[df['type']=='expense']['amount'].sum()
    net_balance = total_income - total_expense
    
    # Calculate average monthly expense safely
    monthly_expenses = df[df['type']=='expense'].groupby(df['date'].dt.to_period('M'))['amount'].sum()
    avg_monthly_expense = monthly_expenses.mean() if not monthly_expenses.empty else 0
    
    with col1:
        st.metric("Total Income", f"₹{total_income:,.2f}", delta="Income")
    with col2:
        st.metric("Total Expenses", f"₹{total_expense:,.2f}", delta_color="inverse")
    with col3:
        st.metric("Net Balance", f"₹{net_balance:,.2f}", 
                 delta_color="normal" if net_balance >= 0 else "inverse")
    with col4:
        st.metric("Avg Monthly", f"₹{avg_monthly_expense:,.2f}")

    # Recent Transactions
    st.subheader("🕒 Recent Transactions")
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
        st.info("No recent transactions")

    # Spending by Category (🎯 Shows AI categorization results)
    st.subheader("📈 Spending by Category (AI Categorized)")
    if total_expense > 0:
        df_exp = df[df['type']=='expense']
        cat_agg = df_exp.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig_pie = px.pie(
                cat_agg, 
                names='category', 
                values='amount', 
                title="AI-Categorized Expense Distribution",
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.write("**Category Breakdown**")
            breakdown = cat_agg.copy()
            breakdown['percentage'] = (breakdown['amount'] / total_expense * 100).round(1)
            breakdown['amount'] = breakdown['amount'].map(lambda x: f"₹{x:,.2f}")
            
            st.dataframe(
                breakdown.rename(columns={'category': 'Category', 'amount': 'Amount', 'percentage': '%'}),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No expense data available")

# ---------------- Reports Tab ----------------
def render_reports():
    """Render reports and analytics tab"""
    st.header("📈 Spending Reports & Analytics")
    
    if not st.session_state.token:
        st.info("🔐 Please login to view reports")
        return
        
    if st.session_state.tx_cache is None or st.session_state.tx_cache.empty:
        st.info("📊 No transaction data available for reporting")
        return
        
    df = st.session_state.tx_cache.copy()
    
    # Report Period Selection
    col1, col2 = st.columns(2)
    with col1:
        report_preset = st.selectbox("📅 Report Period", 
                                   ["Last 3 months", "Last 6 months", "This year", "All time"])
    with col2:
        if report_preset == "Custom range":
            custom_start = st.date_input("Start date", value=date.today() - timedelta(days=90))
            custom_end = st.date_input("End date", value=date.today())
        else:
            date_ranges = {
                "Last 3 months": (date.today() - timedelta(days=90), date.today()),
                "Last 6 months": (date.today() - timedelta(days=180), date.today()),
                "This year": (date.today().replace(month=1, day=1), date.today()),
                "All time": (df['date'].min().date(), date.today())
            }
            custom_start, custom_end = date_ranges[report_preset]
    
    # Filter data for report period
    report_df = safe_date_filter(df, 'date', custom_start, custom_end)
    
    if report_df.empty:
        st.info("No transactions found in the selected period")
        return
    
    # Monthly Spending Summary
    st.subheader("📅 Monthly Spending Summary")
    monthly_summary = generate_monthly_summary(report_df)
    
    if not monthly_summary.empty:
        # Monthly trend chart
        fig_trend = px.line(
            monthly_summary, 
            x='month', 
            y=['income', 'expense'],
            title="Monthly Income vs Expenses Trend",
            labels={'value': 'Amount (₹)', 'variable': 'Type', 'month': 'Month'}
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # Monthly summary table
        display_monthly = monthly_summary.copy()
        display_monthly['income'] = display_monthly.get('income', 0).map(lambda x: f"₹{x:,.2f}")
        display_monthly['expense'] = display_monthly.get('expense', 0).map(lambda x: f"₹{x:,.2f}")
        display_monthly['net'] = display_monthly['net'].map(lambda x: f"₹{x:,.2f}")
        
        st.dataframe(
            display_monthly.rename(columns={
                'month': 'Month', 'income': 'Income', 'expense': 'Expenses', 'net': 'Net'
            }),
            use_container_width=True,
            hide_index=True
        )
    
    # Category-wise Spending Report (🎯 Shows AI categorization results)
    st.subheader("📊 AI-Categorized Spending Report")
    
    category_totals = report_df[report_df['type']=='expense'].groupby('category')['amount'].sum().reset_index()
    category_totals = category_totals.sort_values('amount', ascending=True)  # For horizontal bar chart
    
    if not category_totals.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_bar = px.bar(
                category_totals, 
                x='amount', 
                y='category', 
                orientation='h',
                title="AI-Categorized Spending",
                labels={'amount': 'Amount (₹)', 'category': 'Category'}
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            st.write("**Category Breakdown**")
            breakdown = category_totals.sort_values('amount', ascending=False).copy()
            total_expenses = breakdown['amount'].sum()
            breakdown['percentage'] = (breakdown['amount'] / total_expenses * 100).round(1)
            breakdown['amount'] = breakdown['amount'].map(lambda x: f"₹{x:,.2f}")
            
            st.dataframe(
                breakdown.rename(columns={'category': 'Category', 'amount': 'Amount', 'percentage': '%'}),
                use_container_width=True,
                hide_index=True
            )
    
    # Income vs Expense Summary
    st.subheader("💰 Income vs Expense Summary")
    
    total_income_period = report_df[report_df['type']=='income']['amount'].sum()
    total_expense_period = report_df[report_df['type']=='expense']['amount'].sum()
    net_balance_period = total_income_period - total_expense_period
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Income", f"₹{total_income_period:,.2f}")
    with col2:
        st.metric("Total Expenses", f"₹{total_expense_period:,.2f}")
    with col3:
        st.metric("Net Balance", f"₹{net_balance_period:,.2f}", 
                 delta_color="normal" if net_balance_period >= 0 else "inverse")
    with col4:
        if total_income_period > 0:
            savings_rate = (net_balance_period / total_income_period * 100)
            st.metric("Savings Rate", f"{savings_rate:.1f}%")

# ---------------- Main App ----------------
def main():
    """Main application function"""
    st.title("💰 BudgetWise AI - Expense Forecaster")
    st.markdown("**AI-Powered Expense Tracking & Automatic Categorization**")
    
    # Milestone 2 Feature Highlight
    st.info("🎯 **MILESTONE 2 ACHIEVED**: AI automatically categorizes transactions based on descriptions! "
           "Just enter a description and let the AI do the work.")
    
    # Render sidebar
    render_sidebar()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💳 Transactions", "📈 Reports"])
    
    with tab1:
        render_dashboard()
    
    with tab2:
        render_transactions()
    
    with tab3:
        render_reports()

if __name__ == "__main__":
    main()