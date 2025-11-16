# frontend/admin_dashboard.py

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# Page config
st.set_page_config(
    page_title="BudgetWise Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .admin-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #007bff;
        margin-bottom: 1rem;
    }
    .admin-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
API_BASE = "http://localhost:5000"  # Change if your backend runs elsewhere

def api_request(method, endpoint, token=None, json_data=None):
    """Make API request to backend"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data, timeout=10)
        else:
            return None
        
        return response
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")
        return None

def check_admin_access():
    """Check if current user has admin access"""
    if 'admin_token' not in st.session_state:
        return False
    
    response = api_request("GET", "/admin/check-access", st.session_state.admin_token)
    
    if response and response.status_code == 200:
        data = response.json()
        return data.get('is_admin', False)
    
    return False

def admin_login(email, password):
    """Admin login"""
    response = api_request("POST", "/auth/login", json_data={"email": email, "password": password})
    
    if response and response.status_code == 200:
        data = response.json()
        token = data.get('access_token')
        
        if token:
            # Verify this user is actually an admin
            verify_response = api_request("GET", "/admin/check-access", token)
            if verify_response and verify_response.status_code == 200:
                verify_data = verify_response.json()
                if verify_data.get('is_admin'):
                    st.session_state.admin_token = token
                    st.session_state.admin_email = email
                    return True
                else:
                    st.error("❌ This user is not an administrator")
            else:
                st.error("❌ Failed to verify admin access")
    
    st.error("❌ Login failed. Check your credentials.")
    return False

def render_login():
    """Render admin login form"""
    st.markdown('<div class="admin-header">', unsafe_allow_html=True)
    st.title("🔧 BudgetWise Admin Dashboard")
    st.markdown("System Administration & Analytics")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="admin-warning">', unsafe_allow_html=True)
    st.warning("⚠️ Restricted Access - Administrators Only")
    st.markdown('</div>', unsafe_allow_html=True)
    
    with st.form("admin_login"):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            email = st.text_input("📧 Admin Email", placeholder="your-admin@email.com")
        with col2:
            password = st.text_input("🔒 Password", type="password")
        
        submitted = st.form_submit_button("🚀 Login as Administrator", use_container_width=True)
        
        if submitted:
            if email and password:
                with st.spinner("Verifying admin access..."):
                    if admin_login(email, password):
                        st.success("✅ Admin access granted!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("Please enter both email and password")

def render_dashboard():
    """Render admin dashboard"""
    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown('<div class="admin-header">', unsafe_allow_html=True)
        st.title(f"🔧 BudgetWise Admin Dashboard")
        st.markdown(f"Logged in as: **{st.session_state.admin_email}**")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.metric("🕒", datetime.now().strftime("%H:%M"))
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            for key in ['admin_token', 'admin_email']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Navigation
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", 
        "👥 User Management", 
        "💳 Transactions",
        "📁 Category Management",
        "⚙️ System Tools"
    ])
    
    with tab1:
        render_analytics_dashboard()
    
    with tab2:
        render_user_management()
    
    with tab3:
        render_transaction_view()
    
    with tab4:
        render_category_management()
    
    with tab5:
        render_system_tools()

def render_analytics_dashboard():
    """Render analytics dashboard"""
    st.header("📊 System Analytics")
    
    # Fetch analytics data
    with st.spinner("Loading system analytics..."):
        response = api_request("GET", "/admin/analytics", st.session_state.admin_token)
    
    if not response or response.status_code != 200:
        st.error("❌ Failed to load analytics data")
        return
    
    data = response.json()
    if not data.get('success'):
        st.error(f"❌ {data.get('error', 'Unknown error')}")
        return
    
    analytics = data['analytics']
    
    # Key Metrics
    st.subheader("📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Users", analytics['users']['total'])
        st.metric("Active Users", analytics['users']['active_last_30_days'])
    
    with col2:
        st.metric("Total Transactions", analytics['transactions']['total'])
        st.metric("Transactions Today", analytics['transactions']['today'])
    
    with col3:
        st.metric("Total Goals", analytics['goals']['total'])
        st.metric("Completed Goals", analytics['goals']['completed'])
    
    with col4:
        st.metric("Avg Tx/User", analytics['transactions']['avg_per_user'])
        st.metric("Goal Success Rate", f"{analytics['goals']['completion_rate']}%")
    
    # Charts
    st.subheader("📊 Visual Analytics")
    col1, col2 = st.columns(2)
    
    with col1:
        # User activity chart
        st.write("**User Overview**")
        user_data = {
            'Type': ['Total Users', 'Active Users', 'Inactive Users'],
            'Count': [
                analytics['users']['total'],
                analytics['users']['active_last_30_days'],
                analytics['users']['inactive']
            ]
        }
        fig_users = px.bar(user_data, x='Type', y='Count', color='Type')
        st.plotly_chart(fig_users, use_container_width=True)
    
    with col2:
        # Popular categories
        st.write("**Popular Expense Categories**")
        if analytics['popular_categories']:
            cat_data = pd.DataFrame(analytics['popular_categories'])
            fig_cats = px.pie(cat_data, names='category', values='count')
            st.plotly_chart(fig_cats, use_container_width=True)
        else:
            st.info("No category data available")
    
    # System info
    st.subheader("ℹ️ System Information")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**Last Updated:** {analytics['system']['last_updated']}")
    with col2:
        st.info("**Database:** SQLite")
    with col3:
        st.info("**Status:** 🟢 Operational")

def render_user_management():
    """Render user management section"""
    st.header("👥 User Management")
    
    # Fetch users data
    with st.spinner("Loading users..."):
        response = api_request("GET", "/admin/users", st.session_state.admin_token)
    
    if not response or response.status_code != 200:
        st.error("❌ Failed to load users data")
        return
    
    data = response.json()
    if not data.get('success'):
        st.error(f"❌ {data.get('error', 'Unknown error')}")
        return
    
    users = data['users']
    
    # Users overview
    st.subheader(f"📊 User Overview ({len(users)} Users)")
    
    # Users table
    if users:
        # Prepare data for display
        display_data = []
        for user in users:
            display_data.append({
                'ID': user['id'],
                'Email': user['email'],
                'Joined': user['created_at'][:10] if user['created_at'] else 'N/A',
                'Transactions': user['transaction_count'],
                'Last Activity': user['last_transaction_date'][:10] if user['last_transaction_date'] else 'Never'
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # User statistics
        st.subheader("📈 User Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            active_users = len([u for u in users if u['last_transaction_date']])
            st.metric("Active Users", active_users)
        with col2:
            avg_transactions = sum(u['transaction_count'] for u in users) / len(users) if users else 0
            st.metric("Avg Transactions", round(avg_transactions, 1))
        with col3:
            if users:
                newest_user = max(users, key=lambda x: x['created_at'])
                st.metric("Newest User", newest_user['email'][:15] + "...")
    else:
        st.info("👤 No regular users found in the system")

def render_transaction_view():
    """Render transaction viewing section"""
    st.header("💳 Transaction Overview")
    
    # Fetch transactions
    limit = st.slider("Show last N transactions", 50, 500, 100)
    
    with st.spinner(f"Loading last {limit} transactions..."):
        response = api_request("GET", f"/admin/transactions?limit={limit}", st.session_state.admin_token)
    
    if not response or response.status_code != 200:
        st.error("❌ Failed to load transactions")
        return
    
    data = response.json()
    if not data.get('success'):
        st.error(f"❌ {data.get('error', 'Unknown error')}")
        return
    
    transactions = data['transactions']
    
    st.subheader(f"📋 Recent Transactions ({len(transactions)} loaded)")
    
    if transactions:
        # Prepare data for display
        display_data = []
        for tx in transactions:
            display_data.append({
                'ID': tx['id'],
                'User': tx['user_email'],
                'Date': tx['date'],
                'Amount': f"₹{tx['amount']:,.2f}",
                'Type': tx['type'],
                'Category': tx['category'],
                'Description': tx['description'][:30] + '...' if tx['description'] and len(tx['description']) > 30 else tx['description']
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Transaction insights
        st.subheader("📈 Transaction Insights")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_amount = sum(tx['amount'] for tx in transactions)
            st.metric("Total Amount", f"₹{total_amount:,.2f}")
        
        with col2:
            expense_count = len([tx for tx in transactions if tx['type'] == 'expense'])
            st.metric("Expense Transactions", expense_count)
        
        with col3:
            income_count = len([tx for tx in transactions if tx['type'] == 'income'])
            st.metric("Income Transactions", income_count)
    else:
        st.info("💳 No transactions found from regular users")

def render_category_management():
    """Render category management section"""
    st.header("📁 Category Management")
    
    # Fetch categories data
    with st.spinner("Loading category statistics..."):
        response = api_request("GET", "/admin/categories", st.session_state.admin_token)
    
    if not response or response.status_code != 200:
        st.error("❌ Failed to load categories data")
        return
    
    data = response.json()
    if not data.get('success'):
        st.error(f"❌ {data.get('error', 'Unknown error')}")
        return
    
    categories = data['categories']
    
    st.subheader(f"📊 Category Usage ({len(categories)} Categories)")
    
    if categories:
        # Prepare data for display
        display_data = []
        for cat in categories:
            display_data.append({
                'Category': cat['category'],
                'Transaction Count': cat['transaction_count'],
                'Total Amount': f"₹{cat['total_amount']:,.2f}",
                'Avg Amount': f"₹{cat['avg_amount']:,.2f}",
                'Unique Users': cat['unique_users'],
                'First Used': cat['first_used'][:10] if cat['first_used'] else 'N/A',
                'Last Used': cat['last_used'][:10] if cat['last_used'] else 'N/A'
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Category insights
        st.subheader("📈 Category Insights")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            most_used = max(categories, key=lambda x: x['transaction_count'])
            st.metric("Most Used Category", most_used['category'])
        
        with col2:
            highest_value = max(categories, key=lambda x: x['total_amount'])
            st.metric("Highest Total Value", f"₹{highest_value['total_amount']:,.2f}")
        
        with col3:
            avg_per_category = sum(cat['transaction_count'] for cat in categories) / len(categories)
            st.metric("Avg Tx per Category", round(avg_per_category, 1))
    else:
        st.info("📁 No category data available")
    
    # # Category update tool
    # st.subheader("🔄 Bulk Category Update")
    # st.warning("Use this tool to rename categories across all user transactions")
    
    # with st.form("update_category"):
    #     col1, col2 = st.columns(2)
        
    #     with col1:
    #         old_category = st.text_input("Old Category Name", placeholder="e.g., Shopping")
    #     with col2:
    #         new_category = st.text_input("New Category Name", placeholder="e.g., Retail")
        
    #     submitted = st.form_submit_button("🔄 Update Category", use_container_width=True)
        
    #     if submitted:
    #         if old_category and new_category:
    #             with st.spinner("Updating categories..."):
    #                 response = api_request(
    #                     "POST", 
    #                     "/admin/categories/update", 
    #                     st.session_state.admin_token,
    #                     json_data={"old_category": old_category, "new_category": new_category}
    #                 )
                
    #             if response and response.status_code == 200:
    #                 result = response.json()
    #                 st.success(f"✅ {result.get('message', 'Category updated successfully')}")
    #                 st.rerun()
    #             else:
    #                 st.error("❌ Failed to update category")
    #         else:
    #             st.error("Please enter both old and new category names")

def render_system_tools():
    """Render system monitoring and maintenance tools"""
    st.header("⚙️ System Tools")
    
    # System Health Check
    st.subheader("🩺 System Health Check")
    
    if st.button("🔍 Check System Health", use_container_width=True):
        with st.spinner("Running system health checks..."):
            response = api_request("GET", "/admin/system/health", st.session_state.admin_token)
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get('success'):
                health_checks = data['health_checks']
                
                # Display health metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Database Size", health_checks.get('database_size', 'Unknown'))
                    st.metric("Users Count", health_checks.get('users_count', 'Unknown'))
                
                with col2:
                    st.metric("Transactions Count", health_checks.get('transactions_count', 'Unknown'))
                    st.metric("Goals Count", health_checks.get('financial_goals_count', 'Unknown'))
                
                # with col3:
                #     st.metric("Orphaned Transactions", health_checks.get('orphaned_transactions', 'Unknown'))
                #     st.metric("System Status", health_checks.get('system_status', 'Unknown'))
                
                st.success(f"✅ System health check completed at {data.get('timestamp', 'Unknown')}")
            else:
                st.error("❌ Health check failed")
        else:
            st.error("❌ Failed to run health check")
    
    # Data Cleanup Tools
    # st.subheader("🧹 Data Cleanup")
    # st.warning("Use these tools to clean up orphaned or test data")
    
    # col1, col2 = st.columns(2)
    
    # with col1:
    #     if st.button("🗑️ Clean Orphaned Data", use_container_width=True):
    #         with st.spinner("Cleaning orphaned data..."):
    #             response = api_request(
    #                 "POST", 
    #                 "/admin/system/cleanup", 
    #                 st.session_state.admin_token,
    #                 json_data={"type": "orphaned"}
    #             )
            
    #         if response and response.status_code == 200:
    #             result = response.json()
    #             st.success(f"✅ {result.get('message', 'Cleanup completed')}")
    #             if 'cleanup_results' in result:
    #                 st.json(result['cleanup_results'])
    #         else:
    #             st.error("❌ Cleanup failed")
    
    # with col2:
    #     if st.button("🧪 Clean Test Data", use_container_width=True):
    #         with st.spinner("Cleaning test data..."):
    #             response = api_request(
    #                 "POST", 
    #                 "/admin/system/cleanup", 
    #                 st.session_state.admin_token,
    #                 json_data={"type": "test_data"}
    #             )
            
    #         if response and response.status_code == 200:
    #             result = response.json()
    #             st.success(f"✅ {result.get('message', 'Test data cleanup completed')}")
    #         else:
    #             st.error("❌ Test data cleanup failed")
    
    # System Information
    st.subheader("ℹ️ System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**Backend API:** Running on port 5000")
        st.info("**Database:** SQLite (expense.db)")
    
    with col2:
        st.info("**Admin Dashboard:** Running on port 8502")
        st.info("**User App:** Running on port 8501")
    
    # # Quick Actions
    # st.subheader("🚀 Quick Actions")
    
    # col1, col2, col3 = st.columns(3)
    
    # with col1:
    #     if st.button("🔄 Refresh Cache", use_container_width=True):
    #         st.success("✅ Cache refresh requested")
    
    # with col2:
    #     if st.button("📊 Update Analytics", use_container_width=True):
    #         st.rerun()
    
    # with col3:
    #     if st.button("🔧 Maintenance Mode", use_container_width=True, disabled=True):
    #         st.warning("Maintenance mode would be activated")

def main():
    """Main admin app function"""
    
    # Initialize session state
    if 'admin_token' not in st.session_state:
        st.session_state.admin_token = None
    if 'admin_email' not in st.session_state:
        st.session_state.admin_email = None
    
    # Check if user is logged in as admin
    if st.session_state.admin_token and check_admin_access():
        render_dashboard()
    else:
        render_login()

if __name__ == "__main__":
    main()