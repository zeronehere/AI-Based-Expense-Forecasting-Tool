import sqlite3, os
sql_file = os.path.join(os.path.dirname(__file__), "init_db.sql")
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "expense.db"))
os.makedirs(os.path.dirname(db_path), exist_ok=True)

with open(sql_file, 'r', encoding='utf-8') as f:
    sql = f.read()

conn = sqlite3.connect(db_path)
c = conn.cursor()
c.executescript(sql)
conn.commit()
conn.close()
print("DB initialized at", db_path)
