# backend/app.py
import os
import csv
import io
import logging
from datetime import datetime, timedelta
from collections import OrderedDict

from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

import db
import auth
from categorizer import categorize  # expected to return (category, confidence, suggestions)

# ----- logging -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("expense-backend")

# Supported date formats (try in order)
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]

# ----- Category normalization helper -----
from difflib import get_close_matches

CANONICAL_CATEGORIES = [
    "Groceries", "Transport", "Dining", "Rent", "Utilities", "Entertainment",
    "Healthcare", "Education", "Insurance", "Loan_Repayment", "Salary",
    "Shopping", "Travel", "Miscellaneous", "Uncategorized"
]

def normalize_category(cat):
    """Map incoming category string to a canonical category if close; otherwise return cleaned string."""
    if not cat:
        return "Uncategorized"
    cat = str(cat).strip()
    # exact match (case-insensitive)
    for c in CANONICAL_CATEGORIES:
        if cat.lower() == c.lower():
            return c
    # fuzzy match to canonical list
    match = get_close_matches(cat, CANONICAL_CATEGORIES, n=1, cutoff=0.75)
    if match:
        return match[0]
    # collapse very short or obviously garbage tokens to 'Uncategorized'
    if len(cat) <= 2 or cat.lower() in ("n/a", "na", "none"):
        return "Uncategorized"
    return cat

# ----- Utilities -----
def parse_date(s):
    """Try several common date formats, return datetime.date or None."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    # try ISO parse fallback
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def row_to_dict(row):
    """Convert sqlite3.Row or mapping-like row into plain dict safely."""
    try:
        return dict(row)
    except Exception:
        # fallback if row is a sequence
        try:
            return {k: row[k] for k in range(len(row))}
        except Exception:
            return {}

# ----- Upload limits -----
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS_PER_UPLOAD = 5000

# ----- Flask app factory -----
def create_app():
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key')
    app.register_blueprint(auth.auth_bp, url_prefix='/auth')
    JWTManager(app)

    @app.route('/')
    def root():
        return jsonify({"msg": "Expense Forecaster backend root"})

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok"})

    # ---------------- Transaction creation ----------------
    @app.route('/transactions', methods=['POST'])
    @jwt_required()
    def add_transaction():
        """
        Create a single transaction. If category is missing, call categorizer.
        Expects JSON: {date (ISO), amount, description (optional), type (expense|income), category (optional)}
        """
        # get user id (we stored identity as string earlier)
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({"msg": "Invalid JSON payload"}), 400

        date_str = data.get('date')
        parsed = parse_date(date_str)
        if parsed:
            date_val = parsed.isoformat()
        else:
            return jsonify({"msg": "Invalid or missing date. Use YYYY-MM-DD or similar."}), 400

        try:
            amount = float(data.get('amount', 0))
        except Exception:
            return jsonify({"msg": "Invalid amount; must be numeric."}), 400

        desc = (data.get('description') or '').strip()
        tx_type = data.get('type') or ('income' if amount > 0 else 'expense')
        tx_type = tx_type if tx_type in ('income', 'expense') else 'expense'
        category = data.get('category')  # may be None

        suggestion = None
        if not category or str(category).strip() == '':
            try:
                cat, confidence, suggestions = categorize(desc)
            except Exception as e:
                logger.debug("Categorizer failed: %s", e)
                cat, confidence, suggestions = (None, 0.0, [])
            category = cat or "Uncategorized"
            suggestion = {"category_suggested": cat, "confidence": confidence, "suggestions": suggestions}

        # normalize category to canonical label
        category = normalize_category(category)

        # Insert row
        try:
            tx_id = db.execute_db(
                "INSERT INTO transactions (user_id, date, amount, description, category, type) VALUES (?,?,?,?,?,?)",
                (user_id, date_val, amount, desc, category, tx_type)
            )
        except Exception as e:
            logger.exception("DB insert failed")
            return jsonify({"msg": "DB insert failed", "error": str(e)}), 500

        resp = {
            "msg": "created",
            "transaction_id": tx_id,
            "category": category
        }
        if suggestion:
            resp.update(suggestion)
        return jsonify(resp), 201

    # ---------------- Bulk CSV upload ----------------
    @app.route('/transactions/bulk', methods=['POST'])
    @jwt_required()
    def upload_csv():
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        if 'file' not in request.files:
            return jsonify({"msg": "file required (multipart form-data field 'file')"}), 400

        file = request.files['file']
        filename = secure_filename(file.filename or "upload.csv")

        # simple size guard: read small chunk to estimate
        try:
            # attempt to use content_length if set
            content_length = request.content_length
            if content_length and content_length > MAX_UPLOAD_BYTES:
                return jsonify({"msg": f"File too large. Max {MAX_UPLOAD_BYTES} bytes allowed."}), 413
        except Exception:
            pass

        # read as text safely with fallback encodings
        raw = file.stream.read()
        if not raw:
            return jsonify({"msg": "Empty file"}), 400
        if len(raw) > MAX_UPLOAD_BYTES:
            return jsonify({"msg": f"File too large. Max {MAX_UPLOAD_BYTES} bytes allowed."}), 413

        for encoding in ("utf-8", "latin-1", "utf-16"):
            try:
                content = raw.decode(encoding)
                break
            except Exception:
                content = None
        if content is None:
            return jsonify({"msg": "Could not decode uploaded file"}), 400

        stream = io.StringIO(content)
        reader = csv.DictReader(stream)
        inserted = 0
        errors = []

        for i, row in enumerate(reader, start=1):
            if inserted >= MAX_ROWS_PER_UPLOAD:
                errors.append({"row": i, "reason": "row limit reached"})
                break

            # normalize common column names (case-insensitive)
            date = row.get('date') or row.get('Date') or row.get('transaction_date') or row.get('Transaction_Date') or ''
            parsed = parse_date(date)
            if parsed:
                date_val = parsed.isoformat()
            else:
                errors.append({"row": i, "reason": "invalid date", "raw_date": date})
                continue

            amt_field = row.get('amount') or row.get('Amount') or row.get('amt') or row.get('AMOUNT') or '0'
            try:
                amount = float(amt_field)
            except Exception:
                errors.append({"row": i, "reason": "invalid amount", "raw_amount": amt_field})
                continue

            desc = (row.get('description') or row.get('Description') or row.get('desc') or '').strip()
            tx_type = row.get('type') or row.get('Type') or ('income' if amount > 0 else 'expense')
            if tx_type not in ('income', 'expense'):
                tx_type = 'income' if amount > 0 else 'expense'

            category = row.get('category') or row.get('Category') or ''
            if not category:
                try:
                    cat, confidence, suggestions = categorize(desc)
                except Exception as e:
                    logger.debug("Categorizer failed on row %s: %s", i, e)
                    cat = None
                category = cat or "Uncategorized"

            # normalize category before insert
            category = normalize_category(category)

            try:
                db.execute_db(
                    "INSERT INTO transactions (user_id, date, amount, description, category, type) VALUES (?,?,?,?,?,?)",
                    (user_id, date_val, amount, desc, category, tx_type)
                )
                inserted += 1
            except Exception as e:
                logger.exception("DB error on row %s", i)
                errors.append({"row": i, "reason": "db error", "error": str(e)})
                continue

        return jsonify({"msg": "uploaded", "filename": filename, "inserted": inserted, "errors": errors}), 200

    # ---------------- List transactions ----------------
    @app.route('/transactions', methods=['GET'])
    @jwt_required()
    def list_transactions():
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        try:
            rows = db.query_db(
                "SELECT id, date, amount, description, category, type FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 1000",
                (user_id,)
            )
        except Exception as e:
            logger.exception("DB query failed in list_transactions")
            return jsonify({"msg": "DB query failed", "error": str(e)}), 500

        results = []
        for r in rows:
            try:
                row = dict(r)
            except Exception:
                row = row_to_dict(r)
            # ensure date is ISO string
            if 'date' in row and row['date'] is not None:
                try:
                    parsed = parse_date(row['date'])
                    row['date'] = parsed.isoformat() if parsed else str(row['date'])
                except Exception:
                    row['date'] = str(row['date'])
            results.append(row)
        return jsonify(results)

    # ---------------- Override category ----------------
    @app.route('/transactions/<int:tx_id>/category', methods=['PUT'])
    @jwt_required()
    def override_transaction_category(tx_id):
        """
        Allow the authenticated user to override the category of a transaction they own.
        Body: { "category": "NewCategory" }
        """
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({"msg": "Invalid JSON payload"}), 400

        new_cat = (data.get('category') or '').strip()
        if not new_cat:
            return jsonify({"msg": "category required"}), 400

        # normalize user-provided category
        new_cat = normalize_category(new_cat)

        tx = db.query_db("SELECT * FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id), one=True)
        if not tx:
            return jsonify({"msg": "transaction not found or access denied"}), 404

        try:
            db.execute_db("UPDATE transactions SET category=? WHERE id=? AND user_id=?", (new_cat, tx_id, user_id))
        except Exception as e:
            logger.exception("DB update failed for tx %s", tx_id)
            return jsonify({"msg": "DB update failed", "error": str(e)}), 500

        updated = db.query_db("SELECT id, date, amount, description, category, type FROM transactions WHERE id=?", (tx_id,), one=True)
        if not updated:
            return jsonify({"msg": "updated but could not retrieve"}), 200
        # normalize date in response
        u = dict(updated)
        if 'date' in u and u['date'] is not None:
            p = parse_date(u['date'])
            u['date'] = p.isoformat() if p else str(u['date'])
        return jsonify({"msg": "updated", "transaction": u}), 200

    # ---------------- Reporting endpoints ----------------
    @app.route('/reports/category', methods=['GET'])
    @jwt_required()
    def report_category():
        """
        Returns total expense per category for the last N days (default 30).
        Also provides percent share of total expense.
        Query param: days (int)
        """
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        try:
            days = int(request.args.get('days', 30))
        except Exception:
            days = 30

        since_date = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
        try:
            rows = db.query_db(
                "SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' AND date >= ? GROUP BY category ORDER BY total DESC",
                (user_id, since_date)
            )
        except Exception as e:
            logger.exception("DB query error in report_category")
            return jsonify({"msg": "DB query failed", "error": str(e)}), 500

        results = [dict(r) for r in rows]
        total_expense = sum([float(r.get('total') or 0) for r in results]) or 0.0
        # add percentage
        for r in results:
            t = float(r.get('total') or 0.0)
            r['percent'] = round((t / total_expense * 100), 2) if total_expense else 0.0
        return jsonify({"total_expense": round(total_expense, 2), "by_category": results})

    @app.route('/reports/monthly', methods=['GET'])
    @jwt_required()
    def report_monthly():
        """
        Returns monthly totals for last M months (default 12).
        Output: list of {month: 'YYYY-MM', total_income: <float>, total_expense: <float>}
        """
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        try:
            months = int(request.args.get('months', 12))
        except Exception:
            months = 12

        today = datetime.utcnow().date().replace(day=1)
        # approximate start month by subtracting months*31 days then setting day=1
        start_month = (today - timedelta(days=months*31)).replace(day=1)
        try:
            rows = db.query_db(
                "SELECT date, amount, type FROM transactions WHERE user_id=? AND date >= ?",
                (user_id, start_month.isoformat())
            )
        except Exception as e:
            logger.exception("DB query failed in report_monthly")
            return jsonify({"msg": "DB query failed", "error": str(e)}), 500

        # build months ordered map
        agg = OrderedDict()
        cur = start_month
        while cur <= today:
            key = cur.strftime("%Y-%m")
            agg[key] = {"total_income": 0.0, "total_expense": 0.0}
            # increment month
            year = cur.year + (cur.month // 12)
            month = cur.month % 12 + 1
            cur = cur.replace(year=year, month=month)

        for r in rows:
            d = r.get('date')
            parsed = parse_date(d)
            if not parsed:
                continue
            m = parsed.strftime("%Y-%m")
            amt = float(r.get('amount') or 0.0)
            typ = r.get('type') or 'expense'
            if m not in agg:
                continue
            if typ == 'expense':
                agg[m]['total_expense'] += amt
            else:
                agg[m]['total_income'] += amt

        result = [{"month": k, "total_income": round(v['total_income'], 2), "total_expense": round(v['total_expense'], 2)} for k, v in agg.items()]
        return jsonify(result)

    @app.route('/reports/series', methods=['GET'])
    @jwt_required()
    def report_series():
        """
        Return monthly time series for a specific category over last M months.
        Query params: category (required), months (default 12)
        """
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        category = request.args.get('category')
        if not category:
            return jsonify({"msg": "category query param required"}), 400
        try:
            months = int(request.args.get('months', 12))
        except Exception:
            months = 12

        today = datetime.utcnow().date().replace(day=1)
        start_month = (today - timedelta(days=months*31)).replace(day=1)
        try:
            rows = db.query_db(
                "SELECT date, amount FROM transactions WHERE user_id=? AND date >= ? AND category=?",
                (user_id, start_month.isoformat(), category)
            )
        except Exception as e:
            logger.exception("DB query failed in report_series")
            return jsonify({"msg": "DB query failed", "error": str(e)}), 500

        agg = OrderedDict()
        cur = start_month
        while cur <= today:
            key = cur.strftime("%Y-%m")
            agg[key] = 0.0
            year = cur.year + (cur.month // 12)
            month = cur.month % 12 + 1
            cur = cur.replace(year=year, month=month)

        for r in rows:
            d = r.get('date')
            parsed = parse_date(d)
            if not parsed:
                continue
            m = parsed.strftime("%Y-%m")
            if m not in agg:
                continue
            amt = float(r.get('amount') or 0.0)
            agg[m] += amt

        series = [{"month": k, "total": round(v, 2)} for k, v in agg.items()]
        return jsonify(series)

    @app.route('/reports/summary', methods=['GET'])
    @jwt_required()
    def summary():
        """
        Quick summary: expense totals by category (all-time)
        """
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            user_id = get_jwt_identity()

        try:
            rows = db.query_db("SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' GROUP BY category", (user_id,))
        except Exception as e:
            logger.exception("DB query failed in summary")
            return jsonify({"msg": "DB query failed", "error": str(e)}), 500

        results = [dict(r) for r in rows]
        return jsonify(results)

    # ---------------- Helper endpoint: available categories ----------------
    @app.route('/categories', methods=['GET'])
    def categories():
        """
        Return known category list (static): canonical list plus categorizer keys (if available).
        Useful for the frontend dropdowns.
        """
        try:
            from categorizer import CATEGORY_KEYWORDS
            cats = sorted(set(list(CATEGORY_KEYWORDS.keys()) + CANONICAL_CATEGORIES))
        except Exception:
            cats = sorted(CANONICAL_CATEGORIES)
        return jsonify({"categories": cats})

    return app

# ----- run server (development) -----
if __name__ == '__main__':
    app = create_app()
    # development only; for production use gunicorn/uWSGI
    app.run(debug=True, host='0.0.0.0', port=5000)
