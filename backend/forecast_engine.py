# backend/forecast_engine.py
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

def forecast_expenses(csv_or_df, months_ahead=3):
    """
    Accept either a CSV file path or a pandas DataFrame.
    Returns: (historical_df, forecast_df)
    historical_df: aggregated monthly historical (Date, Amount)
    forecast_df: predicted months with Predicted_Expense
    """
    # Load and preprocess data
    if isinstance(csv_or_df, pd.DataFrame):
        df = csv_or_df.copy()
    else:
        df = pd.read_csv(csv_or_df)

    # Accept several possible column names
    cols = {c.strip(): c for c in df.columns}
    # Normalize column names to standard 'Date' and 'Amount'
    rename_map = {}
    found_date = None
    found_amt = None
    for c in cols:
        lc = c.lower()
        if lc in ('date', 'transaction_date', 'txn_date'):
            found_date = c
        if lc in ('amount', 'amt', 'value'):
            found_amt = c
    if found_date is None or found_amt is None:
        raise ValueError("Data must contain date and amount columns (like 'Date' and 'Amount')")

    df = df.rename(columns={found_date: 'Date', found_amt: 'Amount'})
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)

    # Aggregate by month (end-of-month)
    df = df.set_index('Date').resample('M')['Amount'].sum().reset_index()

    # Prepare features for regression
    df = df.sort_values('Date').reset_index(drop=True)
    df['Month_Number'] = range(1, len(df) + 1)
    X = df[['Month_Number']]
    y = df['Amount']

    # If not enough data points, return historical only
    if len(df) < 2:
        # build forecast dates but keep values NaN
        last = df['Date'].max() if not df.empty else pd.Timestamp.today()
        forecast_dates = pd.date_range(start=last + pd.offsets.MonthBegin(1), periods=months_ahead, freq='MS')
        forecast_df = pd.DataFrame({'Date': forecast_dates, 'Predicted_Expense': [None]*months_ahead})
        return df, forecast_df

    # Train model
    model = LinearRegression()
    model.fit(X, y)

    # Forecast future months
    future_months = np.arange(len(df) + 1, len(df) + months_ahead + 1).reshape(-1, 1)
    predictions = model.predict(future_months)

    # Build forecast DataFrame
    forecast_dates = pd.date_range(
        start=df['Date'].max() + pd.offsets.MonthBegin(1),
        periods=months_ahead,
        freq='MS'
    )

    forecast_df = pd.DataFrame({
        'Date': forecast_dates,
        'Predicted_Expense': predictions
    })

    return df, forecast_df
