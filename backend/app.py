# backend/app.py
import os
import csv
import io
import logging
from datetime import datetime, timedelta
from collections import OrderedDict
from difflib import get_close_matches

from flask import Flask, request, jsonify, g
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from flask_cors import CORS

import db
import auth
from categorizer import categorize  # must return (category, confidence, suggestions)

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("expense-backend")

# ---------------- Constants ----------------
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]
CANONICAL_CATEGORIES = [
    "Groceries", "Transport", "Dining", "Rent", "Utilities", "Entertainment",
    "Healthcare", "Education", "Insurance", "Loan_Repayment", "Salary",
    "Shopping", "Travel", "Miscellaneous", "Uncategorized"
]

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS_PER_UPLOAD = 5000

# ---------------- Helpers ----------------
def normalize_category(cat):
    """Normalize category to canonical list or fallback to Uncategorized"""
    if not cat:
        return "Uncategorized"
    cat = str(cat).strip()
    for c in CANONICAL_CATEGORIES:
        if cat.lower() == c.lower():
            return c
    match = get_close_matches(cat, CANONICAL_CATEGORIES, n=1, cutoff=0.75)
    if match:
        return match[0]
    if len(cat) <= 2 or cat.lower() in ("n/a", "na", "none"):
        return "Uncategorized"
    return cat

def parse_date(s):
    """Try multiple date formats, return datetime.date or None"""
    if not s:
        return None
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def row_to_dict(row):
    """Convert sqlite3.Row or mapping-like row into plain dict"""
    try:
        return dict(row)
    except Exception:
        try:
            return {k: row[k] for k in range(len(row))}
        except Exception:
            return {}

# ---------------- Flask App Factory ----------------
def create_app():
    app = Flask(__name__)

    # JWT secret
    jwt_secret = os.environ.get('JWT_SECRET_KEY', os.urandom(24).hex())
    app.config['JWT_SECRET_KEY'] = jwt_secret
    JWTManager(app)

    # CORS
    cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:8501')
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    CORS(app, resources={r"/*": {"origins": origins}}, supports_credentials=True)

    # Auth blueprint
    app.register_blueprint(auth.auth_bp, url_prefix='/auth')

    # Initialize DB
    with app.app_context():
        db.init_db()
        logger.info("Database initialized or already exists.")

    # Close DB connection after request
    @app.teardown_appcontext
    def close_connection(exception):
        db_conn = getattr(g, '_database', None)
        if db_conn:
            try:
                db_conn.close()
            except Exception:
                logger.exception("Error closing DB connection")

    # ---------------- Root & Health ----------------
    @app.route('/')
    def root():
        return jsonify({"msg": "Expense Forecaster backend root"})

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok"})

    # ---------------- Transaction Endpoints ----------------
    @app.route('/transactions', methods=['POST'])
    @jwt_required()
    def add_transaction():
        """Add a single transaction with auto-categorization"""
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)

        # Parse date
        date_val = parse_date(data.get('date'))
        if not date_val:
            return jsonify({"msg": "Invalid or missing date"}), 400
        date_val = date_val.isoformat()

        # Parse amount
        try:
            amount = float(data.get('amount', 0))
        except Exception:
            return jsonify({"msg": "Invalid amount"}), 400

        # Description and type
        desc = (data.get('description') or '').strip()
        tx_type = data.get('type') or ('income' if amount > 0 else 'expense')
        tx_type = tx_type if tx_type in ('income', 'expense') else 'expense'

        # Category (auto if missing)
        category = data.get('category')
        suggestion = None
        if not category:
            try:
                cat, confidence, suggestions = categorize(desc)
            except Exception:
                cat, confidence, suggestions = ("Uncategorized", "low", [])
            category = cat or "Uncategorized"
            suggestion = {"category_suggested": cat, "confidence": confidence, "suggestions": suggestions}

        category = normalize_category(category)

        # Insert transaction
        try:
            tx_id = db.execute_db(
                "INSERT INTO transactions (user_id, date, amount, description, category, type) VALUES (?,?,?,?,?,?)",
                (user_id, date_val, amount, desc, category, tx_type)
            )
        except Exception as e:
            logger.exception("DB insert failed")
            return jsonify({"msg": "DB insert failed", "error": str(e)}), 500

        resp = {"msg": "created", "transaction_id": tx_id, "category": category}
        if suggestion:
            resp.update(suggestion)
        return jsonify(resp), 201

    @app.route('/transactions/bulk', methods=['POST'])
    @jwt_required()
    def upload_csv():
        """Bulk upload CSV with auto-categorization"""
        user_id = int(get_jwt_identity())
        if 'file' not in request.files:
            return jsonify({"msg": "file required"}), 400

        file = request.files['file']
        filename = secure_filename(file.filename or "upload.csv")
        raw = file.read()
        if not raw:
            return jsonify({"msg": "Empty file"}), 400
        if len(raw) > MAX_UPLOAD_BYTES:
            return jsonify({"msg": f"File too large (> {MAX_UPLOAD_BYTES} bytes)"}), 413

        # Decode CSV
        content = None
        for enc in ("utf-8", "latin-1", "utf-16"):
            try:
                content = raw.decode(enc)
                break
            except Exception:
                continue
        if content is None:
            return jsonify({"msg": "Could not decode file"}), 400

        reader = csv.DictReader(io.StringIO(content))
        inserted, errors = 0, []

        for i, row in enumerate(reader, start=1):
            if inserted >= MAX_ROWS_PER_UPLOAD:
                errors.append({"row": i, "reason": "row limit reached"})
                break
            # Parse date
            date_val = parse_date(row.get('date') or row.get('Date') or '')
            if not date_val:
                errors.append({"row": i, "reason": "invalid date"})
                continue
            date_val = date_val.isoformat()
            # Parse amount
            try:
                amount = float(row.get('amount') or row.get('Amount') or 0)
            except Exception:
                errors.append({"row": i, "reason": "invalid amount"})
                continue
            # Description
            desc = (row.get('description') or row.get('Description') or '').strip()
            if len(desc) > 1000:
                desc = desc[:1000]
            # Type
            tx_type = row.get('type') or ('income' if amount > 0 else 'expense')
            if tx_type not in ('income', 'expense'):
                tx_type = 'income' if amount > 0 else 'expense'
            # Category
            category = row.get('category') or ''
            if not category:
                try:
                    cat, confidence, suggestions = categorize(desc)
                except Exception:
                    cat = "Uncategorized"
                category = cat
            category = normalize_category(category)

            # Insert
            try:
                db.execute_db(
                    "INSERT INTO transactions (user_id, date, amount, description, category, type) VALUES (?,?,?,?,?,?)",
                    (user_id, date_val, amount, desc, category, tx_type)
                )
                inserted += 1
            except Exception as e:
                errors.append({"row": i, "reason": "db error", "error": str(e)})

        return jsonify({"msg": "uploaded", "filename": filename, "inserted": inserted, "errors": errors}), 200

    @app.route('/transactions', methods=['GET'])
    @jwt_required()
    def list_transactions():
        user_id = int(get_jwt_identity())
        rows = db.query_db(
            "SELECT id, date, amount, description, category, type FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 1000",
            (user_id,)
        )
        results = []
        for r in rows:
            row = row_to_dict(r)
            if 'date' in row and row['date'] is not None:
                row['date'] = parse_date(row['date']).isoformat()
            results.append(row)
        return jsonify(results)

    @app.route('/transactions/<int:tx_id>/category', methods=['PUT'])
    @jwt_required()
    def override_transaction_category(tx_id):
        """Allow manual category override"""
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        new_cat = normalize_category(data.get('category'))
        if not new_cat:
            return jsonify({"msg": "category required"}), 400
        tx = db.query_db("SELECT * FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id), one=True)
        if not tx:
            return jsonify({"msg": "transaction not found"}), 404
        db.execute_db("UPDATE transactions SET category=? WHERE id=? AND user_id=?", (new_cat, tx_id, user_id))
        updated = db.query_db("SELECT * FROM transactions WHERE id=?", (tx_id,), one=True)
        u = row_to_dict(updated)
        if 'date' in u and u['date']:
            u['date'] = parse_date(u['date']).isoformat()
        return jsonify({"msg": "updated", "transaction": u})

    # ---------------- Reports ----------------
    @app.route('/reports/category', methods=['GET'])
    @jwt_required()
    def report_category():
        user_id = int(get_jwt_identity())
        days = int(request.args.get('days', 30))
        since_date = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
        rows = db.query_db(
            "SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' AND date >= ? GROUP BY category ORDER BY total DESC",
            (user_id, since_date)
        )
        results = [dict(r) for r in rows]
        total_expense = sum([float(r['total'] or 0) for r in results]) or 0
        for r in results:
            r['percent'] = round((float(r['total'])/total_expense)*100, 2) if total_expense else 0
        return jsonify({"total_expense": round(total_expense, 2), "by_category": results})

    @app.route('/categories', methods=['GET'])
    def categories():
        """Return canonical categories list for frontend dropdowns"""
        return jsonify({"categories": sorted(CANONICAL_CATEGORIES)})

    return app

# ---------------- Run ----------------
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
