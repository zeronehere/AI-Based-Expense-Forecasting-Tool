PRAGMA foreign_keys = ON;

-- Create CATEGORIES table
CREATE TABLE IF NOT EXISTS categories (
    category_name TEXT PRIMARY KEY,
    category_type TEXT CHECK(category_type IN ('income', 'expense')),
    description TEXT
);

-- Create USERS table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create TRANSACTIONS table
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    transaction_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
    description TEXT,
    category_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_name) REFERENCES categories(category_name) ON DELETE SET NULL
);

-- Create FINANCIAL GOALS table
CREATE TABLE IF NOT EXISTS financial_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    goal_name TEXT NOT NULL,
    target_amount DECIMAL(10,2) NOT NULL,
    target_date DATE NOT NULL,
    current_progress DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
