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

🧠 Next Steps (Milestone 3 Preview)

Implement ML-based expense forecasting using linear regression / ARIMA models.

Add category prediction for new transactions.

Display future monthly expenditure graph.

Export visualizations and summaries as reports.

👨‍💻 Author

Project Developer: Zerone Tim
Program: MCA Internship (Infosys Batch 3)
Tools Used: Flask, Streamlit, SQLite, Python, Pandas

Would you like me to extend this documentation with screenshots + graphical architecture diagram (system flow from user → Streamlit → Flask → SQLite)?
That would make it a polished submission-ready report.

You said:
detailed explanation, i want to npresent it\
ChatGPT said:

Perfect 👍 — since you’re going to present this project, here’s a professionally written, detailed documentation version suitable for presentation or report submission (like for an internship milestone review).

It expands the explanations, adds deeper descriptions of the architecture, data flow, and technical decisions.
You can save it as:
📄 AI_Expense_Forecaster_Project_Documentation.docx or .pdf

💰 AI Expense Forecaster

Comprehensive Project Documentation

🧩 Project Overview

The AI Expense Forecaster is an intelligent web-based system designed to help users manage, analyze, and predict their personal or business expenses.

The system enables users to securely log in, record income and expense transactions, upload expense data via CSV files, and visualize their financial patterns.
In later stages, it will use AI models to forecast future expenses based on past spending behavior.

This documentation covers the progress completed in Milestone 1 and Milestone 2, describing the design architecture, implementation details, and user workflow.

🎯 Project Objectives

User Authentication
Allow users to create accounts and log in securely using JWT authentication.

Transaction Management
Provide REST APIs to record and retrieve financial transactions linked to each user.

Data Visualization
Enable users to upload or input data through a web-based dashboard and visualize their income and expense summaries.

Predictive Forecasting (Next Milestone)
Integrate AI models to forecast future monthly or category-wise expenses.

User-Friendly Interface
Simplify financial tracking through an interactive and modern UI built with Streamlit.

🏗️ System Architecture

The project follows a modular client-server architecture:

[ User Interface (Streamlit Frontend) ]
           ↓
   [ Flask REST API Backend ]
           ↓
       [ SQLite Database ]

🔹 Flow Explanation

Frontend (Streamlit)

Acts as the user interaction layer.

Users log in, upload CSV files, and visualize data.

Sends REST API requests to the backend using HTTP.

Backend (Flask API)

Handles user registration, authentication, and data transactions.

Processes and validates all incoming data.

Generates JSON Web Tokens (JWT) to secure API access.

Database (SQLite3)

Stores user credentials and transaction data locally.

Lightweight and easy to integrate for small-to-medium projects.

⚙️ Technology Stack
Layer	Technology	Purpose
Frontend	Streamlit	Interactive dashboard UI
Backend	Flask (Python)	REST API and authentication
Database	SQLite3	Persistent local data storage
Authentication	JWT (JSON Web Token)	Secure user login/session
Visualization	Plotly / Matplotlib	Data charts and summaries
Libraries	Pandas, Werkzeug, Flask-JWT-Extended	Data processing and security
🧱 Project Structure
ai-expense-forecaster/
│
├── backend/
│   ├── app.py                 # Main Flask entry point
│   ├── auth.py                # Authentication routes (Register/Login)
│   ├── transactions.py        # CRUD for transactions
│   ├── db.py                  # Database connection helper
│   ├── check_tables.py        # Debugging tool to verify database
│   └── data/
│       └── expense.db         # SQLite database file
│
├── frontend/
│   └── streamlit_app.py       # Streamlit UI for visualization
│
└── data/
    └── transactions.csv       # Sample CSV file for import

🪜 MILESTONE 1 — Backend Development
🎯 Goal

Develop a secure and functional backend using Flask and SQLite that supports:

User registration and login

JWT-based authentication

Transaction data management

Integration testing via PowerShell

🔹 Step 1: Database Design
1. Table — users
Field	Type	Description
id	INTEGER	Unique user ID
email	TEXT	User email address
password_hash	TEXT	Hashed password for security
2. Table — transactions
Field	Type	Description
id	INTEGER	Transaction ID
user_id	INTEGER	Linked user ID
date	TEXT	Transaction date
amount	REAL	Amount spent or earned
description	TEXT	Description of the transaction
category	TEXT	Type/category (e.g., groceries, rent)
type	TEXT	“income” or “expense”
🔹 Step 2: User Authentication (auth.py)
✅ Registration

Endpoint: /auth/register

Validates email and password input.

Hashes passwords using Werkzeug.

Inserts user data into SQLite.

Sample Request:

{
  "email": "you@example.com",
  "password": "testpass"
}


Response:

{
  "msg": "registered",
  "user_id": 1
}

✅ Login

Endpoint: /auth/login

Verifies user credentials.

On success, generates a JWT access token.

Token is used to access protected endpoints.

Response Example:

{
  "access_token": "eyJhbGciOiJIUzI1...",
  "user_id": 1,
  "email": "you@example.com"
}

🔹 Step 3: Transaction Management (transactions.py)
➤ Add Transaction

POST /transactions

{
  "date": "2025-10-22",
  "amount": 250.5,
  "description": "Grocery store",
  "type": "expense"
}


Stores the record in the database linked to the logged-in user.

➤ Retrieve Transactions

GET /transactions

Returns all transactions belonging to the authenticated user.

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

🔹 Step 4: API Testing (via PowerShell)

The backend was tested using PowerShell’s Invoke-RestMethod:

# Register User
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


All routes worked successfully and returned proper JSON responses.

✅ Milestone 1 Completed

The backend API is:

Stable and secure

Fully integrated with SQLite

JWT-protected

Ready for frontend integration

🪜 MILESTONE 2 — Frontend Integration (Streamlit Dashboard)
🎯 Goal

Develop an interactive Streamlit-based frontend that:

Connects to backend APIs

Allows file uploads (CSV)

Displays analytics and charts

🔹 Step 1: UI Layout Design

Sections:

Header — app title and short description.

Authentication form (email, password).

File upload section for CSV data.

Transaction data table view.

Analytical visualizations and insights.

🔹 Step 2: CSV Upload Functionality

Users can upload a CSV with columns:

date,amount,description,type


Streamlit reads it using Pandas:

import pandas as pd
data = pd.read_csv(uploaded_file)
st.dataframe(data)


Features:

Automatically classifies “income” and “expense”.

Displays total balance, income, and expense.

Supports multiple file formats (.csv, .xlsx).

🔹 Step 3: Data Visualization

Using Matplotlib and Plotly:

Line Chart — Expense trends over time.

Pie Chart — Category-wise expense breakdown.

Bar Graph — Monthly summary.

import matplotlib.pyplot as plt

plt.figure(figsize=(8,4))
plt.plot(data['date'], data['amount'])
st.pyplot(plt)

🔹 Step 4: Backend Connection (optional step completed)

The app can optionally connect with Flask backend APIs to:

Fetch stored transactions.

Display live data.

Synchronize with database entries.

✅ Milestone 2 Completed

The frontend provides:

Clean and simple UI

Upload and analytics options

Functional CSV reading and display

Ready integration with backend

📊 Summary of Achievements
Milestone	Key Deliverables	Status
Milestone 1	Flask backend, JWT, SQLite integration	✅ Completed
Milestone 2	Streamlit dashboard, CSV upload, visualization	✅ Completed
Milestone 3	AI forecasting model, future expense prediction	🚧 In Progress
🧠 Upcoming Milestone 3 (Preview)

The next goal is to implement AI-driven forecasting features:

Apply machine learning models (e.g., Linear Regression, LSTM).

Predict next month’s total expense.

Visualize predicted vs actual spending.