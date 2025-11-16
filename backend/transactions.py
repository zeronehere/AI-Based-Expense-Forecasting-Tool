# backend/transactions.py

from flask import Blueprint, request, jsonify
from .db import get_db
from .categorizer import categorize
from datetime import datetime

bp = Blueprint("transactions", __name__, url_prefix="/transactions")

@bp.route("", methods=["POST"])
def add_transaction():
    db = get_db()
    data = request.get_json()
    date_str = data.get("date")
    amount = data.get("amount")
    desc = data.get("description", "")
    t_type = data.get("type", "expense")
    cat = data.get("category", "")

    # Auto-categorization
    if not cat:
        cat = categorize(desc)

    try:
        date_obj = datetime.fromisoformat(date_str)
    except Exception:
        return jsonify({"msg": "Invalid date format"}), 400

    db.execute(
        "INSERT INTO transactions (date, amount, description, type, category) VALUES (?, ?, ?, ?, ?)",
        (date_obj, amount, desc, t_type, cat)
    )
    db.commit()
    return jsonify({"msg": "Transaction added", "category": cat}), 201

@bp.route("", methods=["GET"])
def get_transactions():
    db = get_db()
    rows = db.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()
    transactions = [dict(row) for row in rows]
    return jsonify(transactions)
