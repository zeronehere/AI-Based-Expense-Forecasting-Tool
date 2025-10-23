import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

def forecast_expenses(csv_path, months_ahead=3):
    # Load and preprocess data
    df = pd.read_csv(csv_path)

    if 'Date' not in df.columns or 'Amount' not in df.columns:
        raise ValueError("CSV must have 'Date' and 'Amount' columns")

    df['Date'] = pd.to_datetime(df['Date'])
    df = df.groupby(pd.Grouper(key='Date', freq='M')).sum().reset_index()

    # Prepare features for regression
    df['Month_Number'] = range(1, len(df) + 1)
    X = df[['Month_Number']]
    y = df['Amount']

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
