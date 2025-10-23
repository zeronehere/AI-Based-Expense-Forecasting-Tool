import sqlite3, os

# adapt path relative to backend/
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "expense.db"))
print("DB path:", db_path)

if not os.path.exists(db_path):
    print("DB file does not exist.")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    print("Tables:", tables)
    conn.close()
