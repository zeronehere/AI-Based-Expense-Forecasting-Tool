# backend/app.py
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import os, csv, io
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
import db
import auth
from categorizer import categorize

DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]

def parse_date(s):
    if not s:
        return None
    s = str(s)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    # try generic parse as fallback
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def create_app():
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key')
    app.register_blueprint(auth.auth_bp, url_prefix='/auth')
    jwt = JWTManager(app)

    @app.route('/')
    def root():
        return "Expense Forecaster backend root"

    @app.route('/health', methods=['GET'])
    def health():
        return {"status":"ok"}

    @app.route('/transactions', methods=['POST'])
    @jwt_required()
    def add_transaction():
        user_id = get_jwt_identity()
        data = request.get_json(force=True)
        date_str = data.get('date')
        parsed = parse_date(date_str)
        date_val = parsed.isoformat() if parsed else date_str
        try:
            amount = float(data.get('amount', 0))
        except:
            return jsonify({"msg":"invalid amount"}), 400
        desc = data.get('description','')
        tx_type = data.get('type','expense')
        category = data.get('category') or categorize(desc)
        tx_id = db.execute_db(
            "INSERT INTO transactions (user_id,date,amount,description,category,type) VALUES (?,?,?,?,?,?)",
            (user_id,date_val,amount,desc,category,tx_type)
        )
        return jsonify({"msg":"created","transaction_id":tx_id}), 201

    @app.route('/transactions/bulk', methods=['POST'])
    @jwt_required()
    def upload_csv():
        user_id = get_jwt_identity()
        if 'file' not in request.files:
            return jsonify({"msg":"file required (multipart form-data field 'file')"}), 400
        file = request.files['file']
        stream = io.StringIO(file.stream.read().decode("utf-8"))
        reader = csv.DictReader(stream)
        inserted = 0
        for row in reader:
            date = row.get('date') or row.get('Date')
            # try parsing date sensibly
            parsed = parse_date(date)
            date_val = parsed.isoformat() if parsed else date
            amt_field = row.get('amount') or row.get('Amount') or row.get('amt') or '0'
            try:
                amount = float(amt_field)
            except:
                amount = 0.0
            desc = row.get('description') or row.get('Description') or ''
            tx_type = row.get('type') or ('income' if amount>0 else 'expense')
            category = row.get('category') or categorize(desc)
            db.execute_db(
                "INSERT INTO transactions (user_id,date,amount,description,category,type) VALUES (?,?,?,?,?,?)",
                (user_id,date_val,amount,desc,category,tx_type)
            )
            inserted += 1
        return jsonify({"msg":"uploaded","inserted":inserted})

    @app.route('/transactions', methods=['GET'])
    @jwt_required()
    def list_transactions():
        user_id = get_jwt_identity()
        rows = db.query_db("SELECT id, date, amount, description, category, type FROM transactions WHERE user_id=? ORDER BY date DESC LIMIT 1000", (user_id,))
        results = [dict(r) for r in rows]
        return jsonify(results)

    # ---------- Reporting endpoints ----------
    @app.route('/reports/category', methods=['GET'])
    @jwt_required()
    def report_category():
        """
        Returns total expense per category for the last N days (default 30).
        Query param: days (int)
        """
        user_id = get_jwt_identity()
        days = int(request.args.get('days', 30))
        since = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
        rows = db.query_db(
            "SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' AND date >= ? GROUP BY category ORDER BY total DESC",
            (user_id, since)
        )
        return jsonify([dict(r) for r in rows])

    @app.route('/reports/monthly', methods=['GET'])
    @jwt_required()
    def report_monthly():
        """
        Returns monthly totals for last M months (default 12).
        Output: list of {month: 'YYYY-MM', total: <float>}
        """
        user_id = get_jwt_identity()
        months = int(request.args.get('months', 12))
        today = datetime.utcnow().date().replace(day=1)
        start_month = (today - timedelta(days=months*31)).replace(day=1)
        rows = db.query_db(
            "SELECT date, amount, type FROM transactions WHERE user_id=? AND date >= ?",
            (user_id, start_month.isoformat())
        )
        # aggregate per month
        agg = OrderedDict()
        # build months list
        months_list = []
        cur = start_month
        while cur <= today:
            key = cur.strftime("%Y-%m")
            agg[key] = 0.0
            months_list.append(key)
            # increment month
            if cur.month == 12:
                cur = cur.replace(year=cur.year+1, month=1)
            else:
                cur = cur.replace(month=cur.month+1)
        for r in rows:
            d = r['date']
            try:
                m = parse_date(d).strftime("%Y-%m")
            except Exception:
                continue
            amt = float(r['amount'] or 0)
            # we include both income and expense (expense subtracts)
            if r['type'] == 'expense':
                agg[m] = agg.get(m, 0.0) + amt
            else:
                agg[m] = agg.get(m, 0.0) + amt
        result = [{"month": k, "total": agg[k]} for k in agg.keys()]
        return jsonify(result)

    @app.route('/reports/series', methods=['GET'])
    @jwt_required()
    def report_series():
        """
        Return monthly time series for a specific category over last M months.
        Query params: category (required), months (default 12)
        """
        user_id = get_jwt_identity()
        category = request.args.get('category')
        if not category:
            return jsonify({"msg":"category query param required"}), 400
        months = int(request.args.get('months', 12))
        today = datetime.utcnow().date().replace(day=1)
        start_month = (today - timedelta(days=months*31)).replace(day=1)
        rows = db.query_db(
            "SELECT date, amount, type, category FROM transactions WHERE user_id=? AND date >= ? AND category=?",
            (user_id, start_month.isoformat(), category)
        )
        # monthly aggregation for that category
        agg = OrderedDict()
        cur = start_month
        while cur <= today:
            key = cur.strftime("%Y-%m")
            agg[key] = 0.0
            if cur.month == 12:
                cur = cur.replace(year=cur.year+1, month=1)
            else:
                cur = cur.replace(month=cur.month+1)
        for r in rows:
            d = r['date']
            try:
                m = parse_date(d).strftime("%Y-%m")
            except Exception:
                continue
            amt = float(r['amount'] or 0)
            agg[m] = agg.get(m, 0.0) + amt
        series = [{"month": k, "total": agg[k]} for k in agg.keys()]
        return jsonify(series)

    # ---------- end reporting ----------

    @app.route('/reports/summary', methods=['GET'])
    @jwt_required()
    def summary():
        user_id = get_jwt_identity()
        rows = db.query_db("SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' GROUP BY category", (user_id,))
        return jsonify([dict(r) for r in rows])

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
