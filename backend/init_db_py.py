# backend/init_db_py.py

import sqlite3
import os

# Define DB path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, '..', 'data')
DB_PATH = os.path.join(DB_DIR, 'expense.db')
SQL_PATH = os.path.join(BASE_DIR, 'init_db.sql')

# Make sure data folder exists
os.makedirs(DB_DIR, exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        print(f"Connected to database at {DB_PATH}")

        # Read and execute the main SQL script
        with open(SQL_PATH, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        cursor.executescript(sql_script)
        
        # 🚨 REMOVED: Admin table creation (since you dropped it manually)
        print("ℹ️  Admin tables skipped (using hardcoded admin)")
        
        conn.commit()
        print("🎉 Database initialized successfully!")

def create_separate_admin_user():
    """Create a separate admin user account"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check if admin user already exists
        cursor.execute("SELECT * FROM users WHERE email=?", ("admin@budgetwise.com",))
        existing_admin = cursor.fetchone()
        
        if not existing_admin:
            # Create separate admin user
            from werkzeug.security import generate_password_hash
            admin_password_hash = generate_password_hash("admin123")  # Default password
            
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                ("admin@budgetwise.com", admin_password_hash)
            )
            
            conn.commit()
            print("✅ Separate admin user created:")
            print("   📧 Email: admin@budgetwise.com")
            print("   🔒 Password: admin123")
            print("   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
            return True
        else:
            print("ℹ️  Separate admin user already exists")
            return False

# 🚨 REMOVED: All admin table functions since table doesn't exist anymore
# - promote_to_admin()
# - demote_from_admin() 
# - list_admin_users()

if __name__ == "__main__":
    print("=" * 50)
    print("🔄 Initializing BudgetWise Database")
    print("=" * 50)
    
    init_db()
    
    print("\n" + "=" * 50)
    print("🔧 Admin Setup")
    print("=" * 50)
    
    print("\n📝 Available Commands:")
    print("   1. Create separate admin user:")
    print("      python -c \"from init_db_py import create_separate_admin_user; create_separate_admin_user()\"")
    print("\n💡 Note: Using hardcoded admin (admin@budgetwise.com)")
    print("   No database admin table required")