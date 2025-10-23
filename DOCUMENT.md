💰 AI Expense Forecaster — Project Documentation
📘 Overview

The AI Expense Forecaster is a smart web-based financial management tool that allows users to record, categorize, and visualize their expenses.
Using machine learning and analytics, it aims to predict future spending patterns based on historical data.

This document covers the completed stages — Milestone 1 and Milestone 2 — including design, architecture, backend APIs, and Streamlit frontend integration.

🎯 Project Objectives

Allow users to register and log in securely.

Provide authenticated access using JWT tokens.

Enable users to add, view, and analyze transactions (income and expenses).

Build a Streamlit-based UI to upload CSV files and visualize expense data.

Prepare the system for AI-based forecasting in later milestones.

🏗️ Tech Stack
Layer	Technology
Frontend	Streamlit
Backend	Flask (Python)
Database	SQLite3
Authentication	JWT (JSON Web Tokens)
Data Handling	Pandas
Environment	Python virtual environment (venv)
⚙️ Project Structure
ai-expense-forecaster/
│
├── backend/
│   ├── app.py                 # Main Flask application entry point
│   ├── auth.py                # Authentication (register & login)
│   ├── transactions.py        # Transaction management routes
│   ├── db.py                  # SQLite database helpers
│   ├── check_tables.py        # DB verification script
│   └── data/
│       └── expense.db         # SQLite database file
│
├── frontend/
│   └── streamlit_app.py       # Streamlit frontend interface
│
└── data/
    └── transactions.csv       # Sample dataset for testing

📍 Milestone 1: Backend Development (User Authentication + Transactions API)
🔹 Goal

To create a secure backend with:

User registration & login

JWT-based authentication

SQLite database integration

Basic CRUD operations for expense transactions

🔹 Features Implemented
1. User Registration (POST /auth/register)

Accepts user email and password.

Passwords are hashed using Werkzeug for security.

Stores user credentials in SQLite.

Sample Request:

POST /auth/register
{
  "email": "you@example.com",
  "password": "testpass"
}


Response:

{
  "msg": "registered",
  "user_id": 1
}

2. User Login (POST /auth/login)

Verifies credentials.

Returns a JWT access token if successful.

Sample Response:

{
  "access_token": "eyJhbGciOiJIUzI1...",
  "user_id": 1,
  "email": "you@example.com"
}

3. Transactions API
➤ Add Transaction

POST /transactions

{
  "date": "2025-10-22",
  "amount": 250.5,
  "description": "Grocery store",
  "type": "expense"
}

➤ View Transactions

GET /transactions

Response:

[
  {
    "id": 1,
    "date": "2025-10-22",
    "amount": 250.5,
    "description": "Grocery store",
    "category": "Groceries",
    "type": "expense"
  }
]

🔹 Database Schema
Table: users
Field	Type	Description
id	INTEGER	Primary key
email	TEXT	Unique email
password_hash	TEXT	Hashed password
Table: transactions
Field	Type	Description
id	INTEGER	Primary key
user_id	INTEGER	Foreign key to users
date	TEXT	Transaction date
amount	REAL	Expense amount
description	TEXT	Transaction details
category	TEXT	Auto-inferred or user-assigned
type	TEXT	'income' or 'expense'
🔹 Testing (PowerShell)

Used PowerShell’s Invoke-RestMethod to test all routes:

# Register
Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/auth/register' `
-ContentType 'application/json' `
-Body '{ "email": "you@example.com", "password": "testpass" }'

# Login
$r = Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/auth/login' `
-ContentType 'application/json' `
-Body '{ "email": "you@example.com", "password": "testpass" }'
$headers = @{ Authorization = "Bearer $($r.access_token)" }

# Add Transaction
Invoke-RestMethod -Method Post -Uri 'http://localhost:5000/transactions' `
-ContentType 'application/json' -Headers $headers `
-Body '{ "date":"2025-10-22", "amount":250.5, "description":"Grocery store", "type":"expense" }'


✅ Milestone 1 Completed

The backend is fully functional, secure, and connected to the database.
All endpoints have been tested successfully using PowerShell.

📍 Milestone 2: Streamlit Frontend (Interactive Dashboard)
🔹 Goal

To design a user-friendly frontend using Streamlit that:

Connects to backend APIs

Allows CSV uploads for expenses

Displays data insights and visualizations

🔹 Features Implemented
1. Streamlit App Structure

File: frontend/streamlit_app.py

Key sections:

Login form (connects to Flask backend)

CSV upload option

Expense table preview

Graphical visualization (spending over time)

2. CSV Upload Functionality

Users can upload a CSV file with columns such as:

date,amount,description,type
2025-10-01,5000,Salary,income
2025-10-02,250,Groceries,expense
2025-10-03,1200,Electricity Bill,expense


Streamlit automatically reads it into a DataFrame and shows:

Total Income

Total Expense

Balance

Monthly Spending Chart

3. Data Visualization

Using Plotly/Matplotlib, charts are generated:

Line chart showing daily expenses

Pie chart showing category-wise spending

🔹 Example Dashboard Sections
Section	Description
Header	App name and short intro
Login	Email + Password
Upload Section	Upload and preview CSV
Analytics	Expense vs Income charts
Summary Metrics	Total spent, total income, net balance

✅ Milestone 2 Completed

Frontend successfully connects with backend.
Users can upload data, visualize it, and manage expenses in a simple interface.