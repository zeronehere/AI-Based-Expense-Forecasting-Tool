# backend/db.py
import sqlite3
from flask import g
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "expense.db"))

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        db = g._database = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    last = cur.lastrowid
    cur.close()
    return last

def init_db():
    """
    Initialize the SQLite database using init_db.sql located in the same backend folder.
    This is idempotent (uses IF NOT EXISTS in SQL) so safe to call at app startup.
    """
    sql_file = os.path.join(os.path.dirname(__file__), "init_db.sql")
    # If SQL file missing, raise so caller can handle/log it
    if not os.path.exists(sql_file):
        raise FileNotFoundError(f"init_db.sql not found at expected path: {sql_file}")

    # Ensure directory exists for DB file
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

    # Execute SQL script against the target DB path
    conn = sqlite3.connect(DB_PATH)
    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
