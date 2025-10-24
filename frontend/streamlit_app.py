# frontend/streamlit_app.py
import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import date, datetime
import io
import plotly.express as px

st.set_page_config(page_title="Expense Forecaster", layout="wide", page_icon="💸")

API_BASE = None
try:
    API_BASE = st.secrets.get("api_base", None)
except Exception:
    API_BASE = None
if not API_BASE:
    API_BASE = "http://localhost:5000"

def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def api_request(method, path, token=None, json=None, files=None, timeout=10):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = API_BASE + path
    try:
        if method.lower() == "get":
            r = requests.get(url, headers=headers, timeout=timeout)
        elif method.lower() == "post":
            r = requests.post(url, headers=headers, json=json, files=files, timeout=timeout)
        elif method.lower() == "put":
            r = requests.put(url, headers=headers, json=json, timeout=timeout)
        else:
            raise ValueError("Unsupported method")
        return r
    except Exception as e:
        return e

def show_response_error(r):
    if isinstance(r, Exception):
        st.error(f"Request failed: {r}")
    else:
        body = safe_json(r)
        if body and isinstance(body, dict) and body.get("msg"):
            st.error(body.get("msg"))
        else:
            st.error(f"Server error (status {getattr(r,'status_code','n/a')}).")
            if hasattr(r, "text"):
                st.code(r.text[:1000])

def normalize_tx_df(df):
    # Accept liberal column names, return standardized df with ['date','amount','description','category','type']
    colmap = {}
    lower_cols = {c.lower(): c for c in df.columns}
    if 'date' in lower_cols:
        colmap[lower_cols['date']] = 'date'
    elif 'transaction_date' in lower_cols:
        colmap[lower_cols['transaction_date']] = 'date'
    if 'amount' in lower_cols:
        colmap[lower_cols['amount']] = 'amount'
    elif 'amt' in lower_cols:
        colmap[lower_cols['amt']] = 'amount'
    if 'description' in lower_cols:
        colmap[lower_cols['description']] = 'description'
    if 'category' in lower_cols:
        colmap[lower_cols['category']] = 'category'
    if 'type' in lower_cols:
        colmap[lower_cols['type']] = 'type'
    df = df.rename(columns=colmap)
    if 'date' not in df.columns or 'amount' not in df.columns:
        raise ValueError("CSV must contain 'date' and 'amount' columns (case-insensitive).")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    if 'description' not in df.columns:
        df['description'] = ''
    if 'category' not in df.columns:
        df['category'] = 'Uncategorized'
    if 'type' not in df.columns:
        df['type'] = df['amount'].apply(lambda x: 'income' if x > 0 else 'expense')
    return df[['date','amount','description','category','type']]

# Session defaults
if "token" not in st.session_state:
    st.session_state.token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "uploaded_df" not in st.session_state:
    st.session_state.uploaded_df = None

# Sidebar - Auth
with st.sidebar:
    st.title("Account")
    if st.session_state.token:
        st.write("Logged in as")
        st.success(st.session_state.user_email or "Unknown")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.user_email = None
    else:
        auth_tab = st.radio("Action", ["Register", "Login"])
        email = st.text_input("Email", key="auth_email")
        pwd = st.text_input("Password", type="password", key="auth_pwd")
        if st.button("Submit"):
            if not email or not pwd:
                st.warning("Please enter both email and password.")
            else:
                if auth_tab == "Register":
                    r = api_request("post", "/auth/register", json={"email": email, "password": pwd})
                    if isinstance(r, Exception) or (hasattr(r, "status_code") and r.status_code != 201):
                        show_response_error(r)
                    else:
                        st.success("Registered — now login.")
                else:
                    r = api_request("post", "/auth/login", json={"email": email, "password": pwd})
                    if isinstance(r, Exception) or (hasattr(r, "status_code") and r.status_code != 200):
                        show_response_error(r)
                    else:
                        payload = safe_json(r)
                        token = payload.get("access_token")
                        if token:
                            st.session_state.token = token
                            st.session_state.user_email = payload.get("email")
                            st.success("Logged in")
                        else:
                            st.error("Login failed: no token returned.")

st.title("Personal Budgeting & Expense Forecaster")

col_main, col_side = st.columns([3, 1])

with col_main:
    st.header("Transactions")
    with st.expander("Manual transaction (quick)"):
        with st.form("manual_tx"):
            d = st.date_input("Date", value=date.today())
            amt = st.number_input("Amount", value=0.0, format="%.2f")
            desc = st.text_input("Description", placeholder="e.g., Grocery store, Salary deposit")
            tx_type = st.selectbox("Type", ("expense", "income"))
            cat = st.text_input("Category (optional)", placeholder="Leave blank to auto-categorize")
            submitted = st.form_submit_button("Add transaction")
        if submitted:
            if not st.session_state.token:
                st.error("Please login first.")
            else:
                payload = {"date": d.isoformat(), "amount": amt, "description": desc, "type": tx_type}
                if cat:
                    payload["category"] = cat
                r = api_request("post", "/transactions", token=st.session_state.token, json=payload)
                if isinstance(r, Exception) or (hasattr(r, "status_code") and r.status_code not in (200,201)):
                    show_response_error(r)
                else:
                    got = safe_json(r) or {}
                    suggested = got.get("category_suggested") or got.get("category")
                    conf = got.get("confidence")
                    if suggested:
                        st.success(f"Transaction added — category: {suggested} (confidence: {conf})")
                    else:
                        st.success("Transaction added.")

    with st.expander("Upload CSV (preview & validate)"):
        uploaded = st.file_uploader("CSV file", type=["csv"], key="uploader")
        if uploaded:
            try:
                df_preview = pd.read_csv(uploaded)
            except Exception as e:
                st.error("Could not read CSV: " + str(e))
                df_preview = None
            if df_preview is not None:
                st.markdown("**Preview (first 10 rows)**")
                st.dataframe(df_preview.head(10))
                st.markdown("**Columns detected:** " + ", ".join(list(df_preview.columns)))
                try:
                    norm = normalize_tx_df(df_preview)
                    st.success("Preview looks good (date & amount detected).")
                    st.session_state.uploaded_df = norm
                except Exception as e:
                    st.warning("Preview validation: " + str(e))
                    st.session_state.uploaded_df = None

                if st.session_state.uploaded_df is not None:
                    if st.button("Upload previewed CSV"):
                        if not st.session_state.token:
                            st.error("Login first.")
                        else:
                            files = {'file': (uploaded.name, uploaded.getvalue())}
                            try:
                                r = requests.post(API_BASE + "/transactions/bulk", headers={"Authorization": f"Bearer {st.session_state.token}"}, files=files, timeout=120)
                            except Exception as e:
                                st.error("Upload failed: " + str(e))
                            else:
                                if getattr(r, "status_code", None) == 200:
                                    payload = safe_json(r) or {}
                                    st.success(f"Uploaded {payload.get('inserted','?')} rows.")
                                else:
                                    show_response_error(r)

    st.header("Reporting — Pie Chart (Spending by Category)")
    st.markdown("Choose a time window and optionally a category filter. The pie chart shows expense distribution by category (percent).")

    # Source selection
    source = st.radio("Data source for reporting", ["Backend (your transactions)", "Uploaded CSV (preview)"], index=0)
    use_df = None
    if source.startswith("Backend"):
        if not st.session_state.token:
            st.info("Login required to fetch backend transactions.")
        else:
            r = api_request("get", "/transactions", token=st.session_state.token)
            if isinstance(r, Exception) or (hasattr(r, "status_code") and r.status_code != 200):
                show_response_error(r)
            else:
                txs = safe_json(r) or []
                df_all = pd.DataFrame(txs)
                if not df_all.empty:
                    df_all['date'] = pd.to_datetime(df_all['date'], errors='coerce')
                    df_all = df_all.dropna(subset=['date'])
                    use_df = normalize_tx_df(df_all)
                else:
                    st.info("No transactions in backend.")
    else:
        if st.session_state.uploaded_df is None:
            st.info("Upload and validate a CSV above first (preview).")
        else:
            use_df = st.session_state.uploaded_df

    if use_df is not None:
        st.subheader("Preview (recent rows)")
        st.dataframe(use_df.sort_values('date', ascending=False).head(50))

        # Dashboard KPIs
        st.markdown("### Summary (selected window)")
        days = st.slider("Days to consider", min_value=7, max_value=365, value=90)
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        recent = use_df[use_df['date'] >= cutoff]
        total_income = recent[recent['type']=='income']['amount'].sum() if not recent.empty else 0.0
        total_expense = recent[recent['type']=='expense']['amount'].sum() if not recent.empty else 0.0
        balance = total_income - total_expense

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Income", f"₹{total_income:,.2f}")
        k2.metric("Total Expense", f"₹{total_expense:,.2f}")
        k3.metric("Balance", f"₹{balance:,.2f}")

        st.markdown("---")
        # Category filter
        categories = ['All'] + sorted(recent['category'].astype(str).unique().tolist())
        sel_cat = st.selectbox("Category (All = show all expense categories)", categories, index=0)

        # Compute category aggregation for pie
        df_exp = recent[recent['type']=='expense'].copy()
        if sel_cat != 'All':
            df_exp = df_exp[df_exp['category'].astype(str).str.lower() == sel_cat.lower()]

        if df_exp.empty:
            st.info("No expense data in the selected window / category.")
        else:
            cat_agg = df_exp.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False)
            cat_agg['percent'] = (cat_agg['amount'] / cat_agg['amount'].sum() * 100).round(2)

            # Pie chart (primary requested change)
            fig = px.pie(cat_agg, names='category', values='amount',
                         title=f"Spending by category — last {days} days",
                         hole=0.4)
            fig.update_traces(textinfo='percent+label', hovertemplate="%{label}: ₹%{value:,.2f} (%{percent})")
            st.plotly_chart(fig, use_container_width=True)

            # Table below pie
            st.markdown("**Category totals**")
            st.dataframe(cat_agg.reset_index(drop=True).assign(amount=lambda df: df['amount'].map(lambda x: f"₹{x:,.2f}")))

        st.markdown("---")
        st.subheader("Monthly totals table (last months)")
        months = st.number_input("Months to show", min_value=1, max_value=36, value=6)
        # build monthly totals (for table view)
        use_df['month'] = use_df['date'].dt.to_period('M').dt.to_timestamp()
        monthly = use_df.groupby('month').apply(lambda g: pd.Series({
            'total_income': g[g['type']=='income']['amount'].sum(),
            'total_expense': g[g['type']=='expense']['amount'].sum()
        })).reset_index().sort_values('month').tail(months)
        if monthly.empty:
            st.info("No monthly data.")
        else:
            monthly_display = monthly.copy()
            monthly_display['total_income'] = monthly_display['total_income'].map(lambda x: f"₹{x:,.2f}")
            monthly_display['total_expense'] = monthly_display['total_expense'].map(lambda x: f"₹{x:,.2f}")
            st.dataframe(monthly_display.rename(columns={'month':'Month','total_income':'Income','total_expense':'Expense'}))

with col_side:
    st.header("Quick Insights")
    if st.session_state.token:
        r = api_request("get", "/transactions", token=st.session_state.token)
        if not isinstance(r, Exception) and getattr(r, "status_code", 0) == 200:
            txs = safe_json(r) or []
            df = pd.DataFrame(txs)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                total_expense = df[df['type']=='expense']['amount'].sum()
                total_income = df[df['type']=='income']['amount'].sum()
                st.metric("Total Expense (all time)", f"₹{total_expense:,.2f}")
                st.metric("Total Income (all time)", f"₹{total_income:,.2f}")
                st.markdown("**Recent transactions**")
                st.table(df.sort_values('date', ascending=False).head(5)[['date','description','amount','category']])
            else:
                st.info("No data yet.")
        else:
            st.info("Login to see insights.")
    else:
        st.info("Login to view personalized insights.")
