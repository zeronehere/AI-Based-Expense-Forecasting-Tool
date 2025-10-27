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

        with open(SQL_PATH, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        cursor.executescript(sql_script)
        conn.commit()
        print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()
