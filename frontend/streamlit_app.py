import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import date
import io
import plotly.express as px
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="Expense Forecaster", layout="wide")

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

def api_request(method, path, token=None, json=None, files=None, timeout=8):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = API_BASE + path
    try:
        if method.lower() == "get":
            r = requests.get(url, headers=headers, timeout=timeout)
        else:
            r = requests.post(url, headers=headers, json=json, files=files, timeout=timeout)
        return r
    except Exception as e:
        return e

def show_response_error(r):
    if isinstance(r, Exception):
        st.error(f"Request failed: {r}")
    else:
        body = safe_json(r)
        if body:
            st.error(body.get("msg", str(body)))
        else:
            st.error(f"Server error (status {r.status_code}).")
            st.code(r.text[:1000])

def normalize_tx_df(df):
    # Accept liberal column names, return standardized df with ['date','amount','description','category','type']
    colmap = {}
    lower_cols = {c.lower(): c for c in df.columns}
    # map common variants
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
    # ensure required columns exist
    if 'date' not in df.columns or 'amount' not in df.columns:
        raise ValueError("CSV must contain 'date' and 'amount' columns (case-insensitive).")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    # default values for optional cols
    if 'description' not in df.columns:
        df['description'] = ''
    if 'category' not in df.columns:
        df['category'] = 'Uncategorized'
    if 'type' not in df.columns:
        # guess type: positive -> income, else expense (user data may vary)
        df['type'] = df['amount'].apply(lambda x: 'income' if x > 0 else 'expense')
    return df[['date','amount','description','category','type']]

def monthly_agg(df, category=None, include_types=None):
    # aggregate df to monthly totals (month start) optionally filtered by category and types
    d = df.copy()
    if category:
        d = d[d['category'].astype(str).str.lower() == str(category).lower()]
    if include_types:
        d = d[d['type'].isin(include_types)]
    if d.empty:
        return pd.DataFrame(columns=['month','amount'])
    d['month'] = d['date'].dt.to_period('M').dt.to_timestamp()
    agg = d.groupby('month')['amount'].sum().reset_index().sort_values('month')
    return agg

def forecast_linear(monthly_df, months_ahead=3):
    # monthly_df: DataFrame with 'month' datetime and 'amount' numeric; returns forecast_df with months ahead
    if monthly_df.empty or len(monthly_df) < 2:
        raise ValueError("Need at least 2 months of data to produce a linear forecast.")
    monthly_df = monthly_df.sort_values('month').reset_index(drop=True)
    monthly_df['t'] = np.arange(1, len(monthly_df) + 1)
    X = monthly_df[['t']].values
    y = monthly_df['amount'].values
    model = LinearRegression()
    model.fit(X, y)
    future_t = np.arange(len(monthly_df) + 1, len(monthly_df) + months_ahead + 1).reshape(-1,1)
    preds = model.predict(future_t)
    last_month = monthly_df['month'].max()
    future_months = pd.date_range(start=(last_month + pd.offsets.MonthBegin(1)).normalize(), periods=months_ahead, freq='MS')
    forecast_df = pd.DataFrame({'month': future_months, 'predicted': preds})
    return forecast_df, model

# Session defaults
if "token" not in st.session_state:
    st.session_state.token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "uploaded_df" not in st.session_state:
    st.session_state.uploaded_df = None

# Sidebar auth
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

st.title("Personal Budgeting & Expense Forecaster — Milestone 2 + Forecasting")

col1, col2 = st.columns([2, 1])

with col1:
    st.header("Transactions")
    with st.expander("Manual transaction (quick)"):
        with st.form("manual_tx"):
            d = st.date_input("Date", value=date.today())
            amt = st.number_input("Amount", value=0.0, format="%.2f")
            desc = st.text_input("Description")
            tx_type = st.selectbox("Type", ("expense", "income"))
            cat = st.text_input("Category (optional)")
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
                        # perform multipart upload to backend
                        files = {'file': (uploaded.name, uploaded.getvalue())}
                        try:
                            r = requests.post(API_BASE + "/transactions/bulk", headers={"Authorization": f"Bearer {st.session_state.token}"}, files=files, timeout=30)
                        except Exception as e:
                            st.error("Upload failed: " + str(e))
                        else:
                            if getattr(r, "status_code", None) == 200:
                                payload = safe_json(r) or {}
                                st.success(f"Uploaded {payload.get('inserted','?')} rows.")
                            else:
                                show_response_error(r)

    st.header("Reporting & Forecasting")
    # Allow use of uploaded CSV or backend data
    source = st.radio("Data source for reporting/forecast", ["Backend (your transactions)", "Uploaded CSV (preview)"], index=0)
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
        st.subheader("Data preview for reports")
        st.dataframe(use_df.sort_values('date', ascending=False).head(50))

        # Filters
        categories = ['All'] + sorted(use_df['category'].astype(str).unique().tolist())
        sel_cat = st.selectbox("Category (select All for overall)", categories, index=0)
        sel_type = st.selectbox("Transaction type", ["expense", "income", "both"], index=0)

        include_types = None
        if sel_type == 'expense':
            include_types = ['expense']
        elif sel_type == 'income':
            include_types = ['income']
        else:
            include_types = ['expense','income']

        # Monthly aggregation
        cat_filter = None if sel_cat == 'All' else sel_cat
        monthly = monthly_agg(use_df, category=cat_filter, include_types=include_types)
        if monthly.empty:
            st.warning("No monthly data after applying filters.")
        else:
            st.markdown("### Monthly totals (aggregated)")
            st.dataframe(monthly)
            fig = px.line(monthly, x='month', y='amount', title='Monthly totals', markers=True)
            st.plotly_chart(fig, use_container_width=True)

            # Forecasting controls
            months_ahead = st.slider("Months to forecast ahead", min_value=1, max_value=24, value=3)
            model_choice = st.selectbox("Forecast model (simple)", ["Linear regression"], index=0)
            if st.button("Run forecast"):
                try:
                    forecast_df, model = forecast_linear(monthly, months_ahead=months_ahead)
                    # prepare combined chart
                    hist = monthly.rename(columns={'amount':'value'}).assign(kind='history')
                    fut = forecast_df.rename(columns={'predicted':'value'}).assign(kind='forecast')
                    combined = pd.concat([hist[['month','value','kind']], fut.rename(columns={'month':'month'})[['month','value','kind']]])
                    combined['month'] = pd.to_datetime(combined['month'])
                    fig2 = px.line(combined, x='month', y='value', color='kind', markers=True, title=f"Historical + Forecast ({months_ahead} months)")
                    st.plotly_chart(fig2, use_container_width=True)
                    st.subheader("Forecast table")
                    st.dataframe(forecast_df)
                except Exception as e:
                    st.error("Forecast failed: " + str(e))

with col2:
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
                st.metric("Total Expense", f"{total_expense:.2f}")
                st.metric("Total Income", f"{total_income:.2f}")
                st.write("Recent transactions:")
                st.write(df.sort_values('date', ascending=False).head(5)[['date','description','amount','category']])
            else:
                st.info("No data yet.")
        else:
            st.info("Login to see insights.")
    else:
        st.info("Login to view personalized insights.")
