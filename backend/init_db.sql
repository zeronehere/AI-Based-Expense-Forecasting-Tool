--backend/init_db.sql

PRAGMA foreign_keys = ON;

-- Create USERS table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create TRANSACTIONS table
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT,
    category TEXT,
    type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create FINANCIAL_GOALS table
CREATE TABLE IF NOT EXISTS financial_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    goal_name TEXT NOT NULL,
    goal_type TEXT CHECK(goal_type IN ('savings', 'spending_reduction', 'category_budget')) NOT NULL,
    target_amount DECIMAL(10,2) NOT NULL,
    current_amount DECIMAL(10,2) DEFAULT 0,
    target_date DATE NOT NULL,
    category TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Goal savings tracking table
CREATE TABLE IF NOT EXISTS goal_savings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    saved_date DATE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (goal_id) REFERENCES financial_goals(id) ON DELETE CASCADE
);

-- 🆕 ADD THESE INDEXES FOR BETTER PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_financial_goals_user_id ON financial_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_goal_savings_goal_id ON goal_savings(goal_id);

-- 🆕 ADD TRIGGER TO AUTO-UPDATE updated_at TIMESTAMP
CREATE TRIGGER IF NOT EXISTS update_financial_goals_timestamp 
AFTER UPDATE ON financial_goals
FOR EACH ROW
BEGIN
    UPDATE financial_goals SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- -- 🆕 ADMIN USERS TABLE
-- CREATE TABLE IF NOT EXISTS admin_users (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     user_id INTEGER NOT NULL UNIQUE,
--     role TEXT DEFAULT 'admin' CHECK(role IN ('admin', 'super_admin')),
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
-- );

-- -- 🆕 Insert yourself as admin (replace YOUR_USER_ID with your actual user ID)
-- -- First, find your user ID from users table, then insert it here
-- -- Example: INSERT INTO admin_users (user_id, role) VALUES (1, 'super_admin');

-- -- 🆕 Create indexes for better performance
-- CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON admin_users(user_id);