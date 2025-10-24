🧾 AI Expense Forecasting Tool — Detailed Project Documentation (Milestone 1 & 2)
🏁 1. Abstract

In the modern world, managing personal finances has become increasingly complex due to the growing number of digital transactions, multiple payment modes, and unpredictable spending habits. The AI Expense Forecasting Tool is designed to simplify financial management by helping users record, categorize, and analyze their income and expenses.
The system provides an interactive web-based interface built using Streamlit or Flask, enabling users to manually input transactions and view their categorized spending reports.

By the completion of Milestone 1 and 2, the project achieves the ability to:

Authenticate users through secure registration and login.

Allow manual transaction input.

Automatically categorize expenses using keyword-based NLP.

Generate visual summaries of spending behavior through basic analytics and charts.

These foundational features lay the groundwork for more advanced forecasting modules to be built in later milestones.

🎯 2. Aim

To design and develop a personal financial management system that enables users to record, categorize, and visualize their expenses and income securely, forming the foundation for future AI-driven expense prediction.

📘 3. Objectives

To create a user authentication system ensuring secure access to personalized financial data.

To build an interface that allows manual entry of transaction data.

To develop a basic rule-based categorization model to classify transactions (Groceries, Rent, Travel, etc.).

To provide visual spending summaries using analytical graphs.

To maintain scalable architecture, allowing future integration of AI/ML-based forecasting modules.

💡 4. Problem Definition

Managing personal finance manually using spreadsheets or notes is inefficient and error-prone. Users often fail to track where their money goes, leading to poor budgeting and uncontrolled expenses.

Existing apps are either too complex or paid, leaving a gap for a simple, open-source, educational, and extendable expense manager that can later support intelligent financial predictions.

Thus, the problem addressed is:

“How to design a simple, modular, and secure system that allows users to input, categorize, and analyze their spending behavior effectively.”

💪 5. Motivation

The project was inspired by:

The lack of free, transparent tools for expense tracking.

The desire to build a foundation for AI-based financial forecasting using real or dummy datasets.

The need for an MVP (Minimum Viable Product) that demonstrates integration of authentication, user data management, NLP-based categorization, and visualization.

🧠 6. System Overview

The system consists of two main phases (Milestone 1 and 2):

Milestone	Focus	Key Deliverables
1 (Weeks 1-2)	User Authentication & Manual Input	Registration, Login, Profile, Transaction Form
2 (Weeks 3-4)	Categorization & Reporting	Rule-Based Categorizer, Summary Reports, Charts

The application uses Streamlit (for UI + backend logic) and SQLite3 (for local data storage).
It follows a modular architecture, meaning each function (auth, input, reports) can later be expanded independently.

⚙️ 7. Technology Stack
Layer	Technology	Reason
Frontend/UI	Streamlit	Simplifies UI + backend in one environment, beginner-friendly, Python-based
Backend	Python (Streamlit/Flask modules)	Handles data input, categorization logic, and chart rendering
Database	SQLite3	Lightweight, file-based DB suitable for single-user MVP
Libraries	Pandas, NLTK, Matplotlib, Seaborn	Used for data manipulation, categorization, and visualization
Security	JWT (JSON Web Token)	Ensures user authentication and session security
🧩 8. Module-Wise Explanation
🔹 Milestone 1: User Authentication & Basic Transaction Input (Weeks 1–2)
Module 1.1: User Registration

Goal: Allow new users to create accounts securely.

Process:

User enters name, email, password.

Passwords are hashed using bcrypt or Python’s hashlib before saving.

Data stored in SQLite table users.

Email uniqueness is enforced.

Output: Confirmation message and stored credentials.

Module 1.2: Login System

Goal: Authenticate registered users.

Process:

Input credentials are verified against stored hashes.

On success, a JWT token or Streamlit session is created.

Invalid credentials prompt an error message.

Security Measures:

JWT-based authentication prevents unauthorized access.

Session timeout after inactivity.

Module 1.3: Profile Management

Goal: Enable users to manage their own financial data.

Features:

Display user profile info.

Update name/email if needed.

Link transaction records to user ID for personalization.

Module 1.4: Manual Transaction Input

Goal: Allow manual entry of dummy transactions.

Interface:

Streamlit form with:

Date picker

Amount input

Description field

Type selector (Income/Expense)

Backend Logic:

Validates numeric and date inputs.

Stores entries in transactions table:

Fields: id, user_id, date, amount, description, type

Outcome: A functioning financial record entry system.

🔹 Milestone 2: Transaction Categorization & Basic Reporting (Weeks 3–4)
Module 2.1: Automated Categorization

Goal: Classify each transaction based on its description.

Technique:

Uses simple NLP keyword matching with NLTK.

Example:

“Uber ride” → Transport

“Supermarket” → Groceries

“Electric bill” → Utilities

A dictionary of keywords and categories is defined.

Allows manual override through dropdown selection.

Output: Updated transaction record with a category field.

Module 2.2: Spending Summary Reports

Goal: Summarize financial data for insights.

Methods:

Pandas used for data aggregation (groupby by category/date).

Computes:

Total spending per category.

Monthly spending summary.

Income vs Expense comparison.

Visuals:

Pie chart for category-wise distribution.

Bar chart for month-wise trends.

Line chart for income-expense comparison.

Module 2.3: Initial Dashboard View

Goal: Display recent transactions and reports in one view.

Design:

Top section: Summary stats (Total income, Total expense, Balance)

Middle: Last 5 transactions

Bottom: Charts (Pie/Bar using Matplotlib)

Outcome: Interactive visual dashboard with instant updates.

🧭 9. Workflow Diagram

Step-by-step Flow:

User registers → login verified.

Dashboard loads → form to add transaction appears.

User enters transaction → system stores it in SQLite.

Categorization engine runs → tags each entry.

Reports generated → charts and summaries shown.

📂 10. Database Design
Table 1: users
Column	Type	Description
id	INTEGER	Primary key
name	TEXT	User name
email	TEXT	Unique
password_hash	TEXT	Encrypted password
Table 2: transactions
Column	Type	Description
id	INTEGER	Primary key
user_id	INTEGER	Linked to users.id
date	TEXT	Transaction date
amount	FLOAT	Amount spent/earned
description	TEXT	Transaction note
type	TEXT	Income/Expense
category	TEXT	Auto-assigned or manual
🔍 11. Testing & Validation
Test Case	Description	Expected Result
User registration	New user signup	Success with stored record
Login validation	Wrong password	Access denied
Transaction input	Valid data	Stored successfully
Categorization	"Bus fare"	Category = Transport
Report generation	Multiple entries	Aggregated summary displayed
🚀 12. Challenges Faced

Designing modular authentication within Streamlit environment.

Ensuring session-based data persistence.

Fine-tuning keyword-based categorization accuracy.

Managing database schema evolution without data loss.

🧩 13. Achievements (Up to Milestone 2)

Secure user registration & login working.

Functional transaction input form.

Categorization engine integrated.

Visual summaries generated successfully.

Initial dashboard interface completed.