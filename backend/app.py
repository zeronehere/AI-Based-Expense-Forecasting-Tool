# backend/app.py

import os
import csv
import io
import logging
import re
from datetime import datetime, timedelta
from difflib import get_close_matches

from flask import Flask, request, jsonify, g
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from flask_cors import CORS

import db
import auth
from categorizer import categorize
from forecast_engine import forecaster  
from goals import GoalManager

# ---------------- Configuration ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("expense-backend")

DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]
CANONICAL_CATEGORIES = [
    "Groceries", "Transport", "Dining", "Rent", "Utilities", "Entertainment",
    "Healthcare", "Education", "Insurance", "Loan_Repayment", "Salary",
    "Shopping", "Travel", "Miscellaneous", "Uncategorized"
]

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS_PER_UPLOAD = 5000
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "expense.db"))

# ---------------- Helpers ----------------
def normalize_category(cat):
    """Normalize category to canonical list"""
    if not cat:
        return "Uncategorized"
    cat = str(cat).strip()
    for c in CANONICAL_CATEGORIES:
        if cat.lower() == c.lower():
            return c
    match = get_close_matches(cat, CANONICAL_CATEGORIES, n=1, cutoff=0.75)
    return match[0] if match else "Uncategorized"

def parse_date(s):
    """Try multiple date formats"""
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
    """Convert sqlite3.Row to dict"""
    try:
        return dict(row)
    except Exception:
        return {col: row[col] for col in row.keys()} if hasattr(row, 'keys') else {}

# 🆕 Fixed Admin helper - only check admin table
def is_admin_user(user_id):
    """Check if user is admin - UPDATED FOR HARCODED ADMIN"""
    try:
        # Get user email
        user = db.query_db("SELECT email FROM users WHERE id=?", (user_id,), one=True)
        
        # Check if it's the hardcoded admin email
        if user and user['email'] == 'admin@budgetwise.com':
            return True
            
        return False
    except Exception as e:
        logger.error(f"Admin check failed: {e}")
        return False

# ---------------- Flask App Factory ----------------
def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', "dev-key-for-mini-project-only")
    JWTManager(app)
    
    # CORS
    cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:8501,http://localhost:8502')
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    CORS(app, resources={r"/*": {"origins": origins}}, supports_credentials=True)
    
    # Blueprints
    app.register_blueprint(auth.auth_bp, url_prefix='/auth')
    
    # Initialize DB
    with app.app_context():
        db.init_db()
        logger.info("Database initialized")
    
    # Teardown
    @app.teardown_appcontext
    def close_connection(exception):
        db_conn = getattr(g, '_database', None)
        if db_conn:
            try:
                db_conn.close()
            except Exception:
                logger.exception("Error closing DB connection")
    
    # ---------------- Core Endpoints ----------------
    @app.route('/')
    def root():
        return jsonify({"msg": "Expense Forecaster backend root"})
    
    @app.route('/health')
    def health():
        return jsonify({"status": "ok"})
    
    @app.route('/categories')
    def categories():
        return jsonify({"categories": sorted(CANONICAL_CATEGORIES)})
    
    # ---------------- Transaction Endpoints ----------------
    def handle_transaction_data(user_id, data, is_bulk=False):
        """Process transaction data (single or bulk)"""
        date_val = parse_date(data.get('date'))
        if not date_val:
            return None, "Invalid or missing date"
        
        # Better amount parsing with validation
        amount_str = str(data.get('amount', '0')).strip()
        amount_str = re.sub(r'[^\d.-]', '', amount_str)
        
        try:
            amount = float(amount_str)
            # Validate reasonable amount range
            if abs(amount) > 10000000:  # 1 crore limit
                return None, f"Amount too large: {amount}"
            if amount == 0:
                return None, "Amount cannot be zero"
        except Exception as e:
            logger.error(f"Amount parsing failed: {amount_str}, error: {e}")
            return None, "Invalid amount format"
        
        desc = (data.get('description') or '').strip()[:1000]
        tx_type = data.get('type') or ('income' if amount > 0 else 'expense')
        tx_type = tx_type if tx_type in ('income', 'expense') else 'expense'
        
        category = data.get('category')
        if not category:
            try:
                cat, confidence, suggestions = categorize(desc)
                category = cat if cat else "Uncategorized"
            except Exception:
                category = "Uncategorized"
        
        category = normalize_category(category)
        return {
            'user_id': user_id,
            'date': date_val.isoformat(),
            'amount': amount,
            'description': desc,
            'category': category,
            'type': tx_type
        }, None
    
    @app.route('/transactions', methods=['POST'])
    @jwt_required()
    def add_transaction():
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        
        tx_data, error = handle_transaction_data(user_id, data)
        if error:
            return jsonify({"msg": error}), 400
        
        try:
            tx_id = db.execute_db(
                "INSERT INTO transactions (user_id, date, amount, description, category, type) VALUES (?,?,?,?,?,?)",
                (tx_data['user_id'], tx_data['date'], tx_data['amount'], 
                 tx_data['description'], tx_data['category'], tx_data['type'])
            )
            return jsonify({"msg": "created", "transaction_id": tx_id, "category": tx_data['category']}), 201
        except Exception as e:
            logger.exception("DB insert failed")
            return jsonify({"msg": "DB insert failed", "error": str(e)}), 500
    
    @app.route('/transactions/bulk', methods=['POST'])
    @jwt_required()
    def upload_csv():
        user_id = int(get_jwt_identity())
        if 'file' not in request.files:
            return jsonify({"msg": "file required"}), 400
        
        file = request.files['file']
        raw = file.read()
        if not raw or len(raw) > MAX_UPLOAD_BYTES:
            return jsonify({"msg": "Empty file or too large"}), 400
        
        # Decode CSV
        content = None
        for enc in ("utf-8", "latin-1", "utf-16"):
            try:
                content = raw.decode(enc)
                break
            except Exception:
                continue
        if not content:
            return jsonify({"msg": "Could not decode file"}), 400
        
        reader = csv.DictReader(io.StringIO(content))
        inserted, errors = 0, []
        
        for i, row in enumerate(reader, start=1):
            if inserted >= MAX_ROWS_PER_UPLOAD:
                break
            
            tx_data, error = handle_transaction_data(user_id, row, is_bulk=True)
            if error:
                errors.append({"row": i, "reason": error})
                continue
            
            try:
                db.execute_db(
                    "INSERT INTO transactions (user_id, date, amount, description, category, type) VALUES (?,?,?,?,?,?)",
                    (tx_data['user_id'], tx_data['date'], tx_data['amount'], 
                     tx_data['description'], tx_data['category'], tx_data['type'])
                )
                inserted += 1
            except Exception as e:
                errors.append({"row": i, "reason": "db error", "error": str(e)})
        
        return jsonify({
            "msg": "uploaded", 
            "filename": secure_filename(file.filename or "upload.csv"),
            "inserted": inserted, 
            "errors": errors
        }), 200
    
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
            if 'date' in row and row['date']:
                row['date'] = parse_date(row['date']).isoformat()
            results.append(row)
        return jsonify(results)
    
    @app.route('/transactions/<int:tx_id>/category', methods=['PUT'])
    @jwt_required()
    def override_transaction_category(tx_id):
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        new_cat = normalize_category(data.get('category'))
        
        if not new_cat:
            return jsonify({"msg": "category required"}), 400
        
        tx = db.query_db("SELECT * FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id), one=True)
        if not tx:
            return jsonify({"msg": "transaction not found"}), 404
        
        db.execute_db("UPDATE transactions SET category=? WHERE id=? AND user_id=?", (new_cat, tx_id, user_id))
        return jsonify({"msg": "updated", "category": new_cat})
    
    # ---------------- Reports ----------------
    @app.route('/reports/category', methods=['GET'])
    @jwt_required()
    def report_category():
        user_id = int(get_jwt_identity())
        days = int(request.args.get('days', 30))
        since_date = (datetime.now().date() - timedelta(days=days)).isoformat()
        
        rows = db.query_db(
            "SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' AND date >= ? GROUP BY category ORDER BY total DESC",
            (user_id, since_date)
        )
        
        results = [dict(r) for r in rows]
        total_expense = sum(float(r['total'] or 0) for r in results) or 0
        
        for r in results:
            r['percent'] = round((float(r['total'])/total_expense)*100, 2) if total_expense else 0
        
        return jsonify({"total_expense": round(total_expense, 2), "by_category": results})
    
    @app.route('/reports/monthly', methods=['GET'])
    @jwt_required()
    def report_monthly():
        user_id = int(get_jwt_identity())
        months = int(request.args.get('months', 6))
        start_date = (datetime.now().date().replace(day=1) - timedelta(days=30*months)).isoformat()
        
        rows = db.query_db("""
            SELECT strftime('%Y-%m', date) as month,
                   SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
            FROM transactions 
            WHERE user_id=? AND date >= ?
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month DESC
        """, (user_id, start_date))
        
        results = [dict(r) for r in rows]
        for r in results:
            r['net'] = r['income'] - r['expense']
            
        return jsonify({"monthly_summary": results})
    
    @app.route('/reports/overview', methods=['GET'])
    @jwt_required()
    def report_overview():
        user_id = int(get_jwt_identity())
        
        # Get totals
        income_row = db.query_db("SELECT SUM(amount) as total FROM transactions WHERE user_id=? AND type='income'", (user_id,), one=True)
        expense_row = db.query_db("SELECT SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense'", (user_id,), one=True)
        recent_count_row = db.query_db("SELECT COUNT(*) as count FROM transactions WHERE user_id=? AND date >= date('now', '-30 days')", (user_id,), one=True)
        
        total_income = float(income_row['total'] or 0)
        total_expense = float(expense_row['total'] or 0)
        
        return jsonify({
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "net_balance": round(total_income - total_expense, 2),
            "recent_transactions": recent_count_row['count']
        })
    
    # ---------------- Advanced Forecasting Endpoints ----------------
    @app.route('/forecast', methods=['POST'])
    @jwt_required()
    def generate_forecast():
        """Generate advanced expense forecast"""
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        
        category = data.get('category', 'all')
        months_ahead = min(int(data.get('months_ahead', 6)), 12)
        frequency = data.get('frequency', 'D')  # D: daily, W: weekly, M: monthly
        
        logger.info(f"🔮 Forecast request - User: {user_id}, Category: {category}, Months: {months_ahead}")
        
        # Get user transactions
        rows = db.query_db(
            "SELECT date, amount, category, type FROM transactions WHERE user_id=? ORDER BY date",
            (user_id,)
        )
        
        if not rows:
            logger.warning(f"No transactions found for user {user_id}")
            return jsonify({"error": "No transaction data available for forecasting"}), 400
        
        logger.info(f"📊 Found {len(rows)} transactions for forecasting")
        
        # Convert to list of dicts
        transactions = []
        for row in rows:
            tx = row_to_dict(row)
            if 'date' in tx and tx['date']:
                tx['date'] = parse_date(tx['date']).isoformat()
            transactions.append(tx)
        
        # Generate advanced forecast
        logger.info("🔄 Generating forecast...")
        forecast_result, error = forecaster.generate_forecast(
            transactions, category, months_ahead, frequency
        )
        
        if error:
            logger.error(f"❌ Forecast failed: {error}")
            return jsonify({"error": error}), 500
        
        logger.info("✅ Forecast generated successfully")
        return jsonify({
            "success": True,
            "forecast": forecast_result,
            "parameters": {
                "category": category,
                "months_ahead": months_ahead,
                "frequency": frequency
            }
        })
    
    @app.route('/forecast/categories', methods=['GET'])
    @jwt_required()
    def get_forecast_categories():
        user_id = int(get_jwt_identity())
        
        try:
            rows = db.query_db(
                "SELECT DISTINCT category FROM transactions WHERE user_id=? AND type='expense' AND category IS NOT NULL",
                (user_id,)
            )
            
            categories = [row['category'] for row in rows if row['category']]
            categories.insert(0, 'all')
            
            logger.info(f"📋 Found {len(categories)} forecast categories for user {user_id}")
            
            return jsonify({"categories": categories})
            
        except Exception as e:
            logger.error(f"Error getting forecast categories: {str(e)}")
            # Return default categories if query fails
            return jsonify({"categories": ["all", "Groceries", "Transport", "Dining", "Shopping", "Entertainment"]})
    
    @app.route('/forecast/compare', methods=['POST'])
    @jwt_required()
    def compare_forecasts():
        """Compare forecasts across multiple categories"""
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        
        categories = data.get('categories', ['all'])
        months_ahead = min(int(data.get('months_ahead', 6)), 12)
        
        logger.info(f"🔮 Compare forecast request - User: {user_id}, Categories: {categories}")
        
        # Get user transactions
        rows = db.query_db(
            "SELECT date, amount, category, type FROM transactions WHERE user_id=? ORDER BY date",
            (user_id,)
        )
        
        if not rows:
            return jsonify({"error": "No transaction data available"}), 400
        
        transactions = []
        for row in rows:
            tx = row_to_dict(row)
            if 'date' in tx and tx['date']:
                tx['date'] = parse_date(tx['date']).isoformat()
            transactions.append(tx)
        
        # Generate multiple forecasts
        logger.info(f"🔄 Generating {len(categories)} forecasts...")
        forecasts = forecaster.generate_multiple_forecasts(
            transactions, categories, months_ahead
        )
        
        logger.info("✅ Multiple forecasts generated successfully")
        return jsonify({
            "success": True,
            "forecasts": forecasts,
            "parameters": {
                "categories": categories,
                "months_ahead": months_ahead
            }
        })
    
    @app.route('/forecast/performance', methods=['GET'])
    @jwt_required()
    def get_forecast_performance():
        """Get forecast model performance metrics"""
        user_id = int(get_jwt_identity())
        
        # Get performance metrics from advanced forecaster
        performance_metrics = forecaster.performance_metrics
        
        return jsonify({
            "success": True,
            "performance_metrics": performance_metrics,
            "model_info": {
                "name": "Advanced Prophet with Fallback",
                "version": "1.0",
                "features": [
                    "Holiday integration",
                    "Anomaly detection", 
                    "Multiple seasonalities",
                    "Simple fallback model",
                    "Trend analysis"
                ]
            }
        })
    
    # ---------------- Goals Endpoints ----------------
    @app.route('/goals', methods=['POST'])
    @jwt_required()
    def create_goal():
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        
        required_fields = ['goal_name', 'goal_type', 'target_amount', 'target_date']
        if any(field not in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        
        try:
            # Validate target date
            target_date = datetime.strptime(data['target_date'], '%Y-%m-%d').date()
            if target_date < datetime.now().date():
                return jsonify({"error": "Target date cannot be in the past"}), 400
            
            # Insert goal
            goal_id = db.execute_db(
                """INSERT INTO financial_goals 
                (user_id, goal_name, goal_type, target_amount, target_date, category, description) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    data['goal_name'],
                    data['goal_type'],
                    float(data['target_amount']),
                    data['target_date'],
                    data.get('category'),
                    data.get('description', '')
                )
            )
            
            if goal_id:
                logger.info(f"✅ Goal created successfully - ID: {goal_id}")
                return jsonify({
                    "success": True, 
                    "goal_id": goal_id,
                    "message": "Goal created successfully"
                }), 201
            else:
                logger.error("❌ Failed to create goal - no ID returned")
                return jsonify({"error": "Failed to create goal - no ID returned"}), 500
                
        except Exception as e:
            logger.error(f"Error creating goal: {str(e)}")
            return jsonify({"error": f"Failed to create goal: {str(e)}"}), 500

    @app.route('/goals', methods=['GET'])
    @jwt_required()
    def get_goals():
        user_id = int(get_jwt_identity())
        
        try:
            goals = db.query_db(
                "SELECT * FROM financial_goals WHERE user_id = ? ORDER BY created_at DESC", 
                (user_id,)
            )
            
            goals_list = []
            for goal in goals:
                # FIXED: Get exact values from database without any processing
                goal_dict = {
                    'id': goal['id'],
                    'user_id': goal['user_id'],
                    'goal_name': goal['goal_name'],
                    'goal_type': goal['goal_type'],
                    'target_amount': float(goal['target_amount']),  # Direct from DB
                    'current_amount': float(goal['current_amount']),  # Direct from DB
                    'target_date': goal['target_date'],
                    'category': goal['category'],
                    'description': goal['description'],
                    'created_at': goal['created_at'],
                    'updated_at': goal['updated_at']
                }
                
                # Log the exact values for debugging
                logger.info(f"🎯 Goal {goal['id']}: Target={goal['target_amount']}, Current={goal['current_amount']}")
                
                # Calculate progress
                if goal_dict['target_amount'] > 0:
                    goal_dict['progress_percent'] = min(100, (goal_dict['current_amount'] / goal_dict['target_amount']) * 100)
                else:
                    goal_dict['progress_percent'] = 0
                
                # Calculate days remaining
                try:
                    target_date = datetime.strptime(goal_dict['target_date'], '%Y-%m-%d').date()
                    days_remaining = (target_date - datetime.now().date()).days
                    goal_dict['days_remaining'] = max(0, days_remaining)
                except:
                    goal_dict['days_remaining'] = 0
                
                # Set status
                if goal_dict['progress_percent'] >= 100:
                    goal_dict['status'] = 'achieved'
                elif goal_dict['days_remaining'] <= 0:
                    goal_dict['status'] = 'overdue'
                else:
                    goal_dict['status'] = 'active'
                    
                goals_list.append(goal_dict)
            
            logger.info(f"📋 Retrieved {len(goals_list)} goals for user {user_id}")
            return jsonify({
                "success": True,
                "goals": goals_list
            })
            
        except Exception as e:
            logger.error(f"Error fetching goals: {str(e)}")
            return jsonify({"error": f"Failed to fetch goals: {str(e)}"}), 500

    @app.route('/goals/<int:goal_id>', methods=['DELETE'])
    @jwt_required()
    def delete_goal(goal_id):
        user_id = int(get_jwt_identity())
        logger.info(f"🗑️ Delete goal request - Goal ID: {goal_id}, User ID: {user_id}")
        
        try:
            # Verify the goal exists and belongs to the user
            goal = db.query_db(
                "SELECT * FROM financial_goals WHERE id=? AND user_id=?", 
                (goal_id, user_id), 
                one=True
            )
            
            if not goal:
                logger.warning(f"Goal {goal_id} not found for user {user_id}")
                return jsonify({"error": "Goal not found or access denied"}), 404
            
            # Delete the goal
            db.execute_db(
                "DELETE FROM financial_goals WHERE id=? AND user_id=?", 
                (goal_id, user_id)
            )
            
            logger.info(f"✅ Goal {goal_id} deleted successfully for user {user_id}")
            return jsonify({
                "success": True, 
                "message": "Goal deleted successfully",
                "deleted_goal_id": goal_id
            })
            
        except Exception as e:
            logger.error(f"❌ Error deleting goal {goal_id}: {str(e)}")
            return jsonify({"error": f"Failed to delete goal: {str(e)}"}), 500

    @app.route('/goals/progress', methods=['GET'])
    @jwt_required()
    def get_goals_progress():
        """Get goals with progress"""
        user_id = int(get_jwt_identity())
        
        try:
            # Get goals with current progress
            goal_manager = GoalManager(DB_PATH)
            goals, error = goal_manager.get_user_goals(user_id)
            if error:
                return jsonify({"error": error}), 500
            
            return jsonify({"success": True, "goals": goals})
            
        except Exception as e:
            logger.error(f"Error getting goals progress: {str(e)}")
            return jsonify({"error": "Failed to get goals progress"}), 500

    # 🆕 NEW: Add savings to goal
    @app.route('/goals/<int:goal_id>/savings', methods=['POST'])
    @jwt_required()
    def add_goal_savings(goal_id):
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        
        # Verify goal belongs to user
        goal = db.query_db("SELECT * FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id), one=True)
        if not goal:
            return jsonify({"error": "Goal not found"}), 404
        
        amount = data.get('amount', 0)
        description = data.get('description', '')
        
        if amount <= 0:
            return jsonify({"error": "Amount must be positive"}), 400
        
        goal_manager = GoalManager(DB_PATH)
        success, message = goal_manager.add_savings_to_goal(goal_id, amount, description)
        if success:
            # Get updated goal
            updated_goal = db.query_db("SELECT * FROM financial_goals WHERE id=?", (goal_id,), one=True)
            return jsonify({
                "success": True, 
                "message": message,
                "goal": {
                    "current_amount": float(updated_goal['current_amount']),
                    "progress_percent": min(100, (float(updated_goal['current_amount']) / float(updated_goal['target_amount'])) * 100)
                }
            })
        else:
            return jsonify({"error": message}), 400

    # 🆕 NEW: Get savings history for goal
    @app.route('/goals/<int:goal_id>/savings', methods=['GET'])
    @jwt_required()
    def get_goal_savings(goal_id):
        user_id = int(get_jwt_identity())
        
        # Verify goal belongs to user
        goal = db.query_db("SELECT * FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id), one=True)
        if not goal:
            return jsonify({"error": "Goal not found"}), 404
        
        goal_manager = GoalManager(DB_PATH)
        savings, error = goal_manager.get_goal_savings_history(goal_id)
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({"savings": savings})

    # 🆕 UPDATED: Goal coaching
    @app.route('/goals/<int:goal_id>/coaching', methods=['GET'])
    @jwt_required()
    def get_goal_coaching(goal_id):
        """Get AI coaching analysis for a specific goal"""
        user_id = int(get_jwt_identity())
        
        try:
            # Get user transactions for AI analysis
            rows = db.query_db(
                "SELECT date, amount, category, type FROM transactions WHERE user_id=? ORDER BY date",
                (user_id,)
            )
            
            transactions = []
            for row in rows:
                tx = row_to_dict(row)
                if 'date' in tx and tx['date']:
                    tx['date'] = parse_date(tx['date']).isoformat()
                transactions.append(tx)
            
            # Get AI coaching
            goal_manager = GoalManager(DB_PATH)
            coaching_result, error = goal_manager.get_goal_coaching(
                user_id, goal_id, transactions
            )
            
            if error:
                return jsonify({"error": error}), 400
            
            return jsonify({
                "success": True,
                "coaching": coaching_result
            })
            
        except Exception as e:
            logger.error(f"Goal coaching error: {str(e)}")
            return jsonify({"error": "Failed to generate coaching analysis"}), 500

    # 🆕 NEW: Goal Analytics Endpoint
    @app.route('/goals/analytics', methods=['GET'])
    @jwt_required()
    def get_goals_analytics():
        """Get analytics for all user goals"""
        user_id = int(get_jwt_identity())
        
        goal_manager = GoalManager(DB_PATH)
        analytics, error = goal_manager.get_goal_analytics(user_id)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "success": True,
            "analytics": analytics
        })
    
    # ---------------- Admin Endpoints ----------------
    @app.route('/admin/check-access', methods=['GET'])
    @jwt_required()
    def admin_check_access():
        """Check if user has admin access"""
        user_id = int(get_jwt_identity())
        is_admin = is_admin_user(user_id)
        
        # Also get user email for display
        user = db.query_db("SELECT email FROM users WHERE id=?", (user_id,), one=True)
        user_email = user['email'] if user else None
        
        return jsonify({
            "is_admin": is_admin,
            "user_email": user_email
        })

    @app.route('/admin/users', methods=['GET'])
    @jwt_required()
    def admin_get_users():
        """Get all users (admin only) - EXCLUDES ADMIN USER"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            # 🆕 UPDATED: Exclude admin user from the list
            users = db.query_db('''
                SELECT u.id, u.email, u.created_at, 
                    COUNT(t.id) as transaction_count,
                    MAX(t.date) as last_transaction_date
                FROM users u
                LEFT JOIN transactions t ON u.id = t.user_id
                WHERE u.email != 'admin@budgetwise.com'  -- 🆕 CHANGED: Exclude hardcoded admin
                GROUP BY u.id
                ORDER BY u.created_at DESC
            ''')
            
            users_list = []
            for user in users:
                user_dict = dict(user)
                # Convert dates to string for JSON
                if user_dict['created_at']:
                    user_dict['created_at'] = str(user_dict['created_at'])
                if user_dict['last_transaction_date']:
                    user_dict['last_transaction_date'] = str(user_dict['last_transaction_date'])
                users_list.append(user_dict)
            
            return jsonify({
                "success": True,
                "users": users_list,
                "total_users": len(users_list)
            })
        except Exception as e:
            logger.error(f"Admin users fetch failed: {e}")
            return jsonify({"error": "Failed to fetch users"}), 500
    
    @app.route('/admin/transactions', methods=['GET'])
    @jwt_required()
    def admin_get_all_transactions():
        """Get all transactions across all users (admin only) - EXCLUDES ADMIN TRANSACTIONS"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            limit = min(int(request.args.get('limit', 100)), 1000)  # Max 1000 for safety
            
            # 🆕 UPDATED: Exclude admin user's transactions
            transactions = db.query_db('''
                SELECT t.*, u.email as user_email
                FROM transactions t
                JOIN users u ON t.user_id = u.id
                WHERE u.email != 'admin@budgetwise.com'  -- 🆕 CHANGED: Exclude hardcoded admin
                ORDER BY t.date DESC
                LIMIT ?
            ''', (limit,))
            
            transactions_list = []
            for tx in transactions:
                tx_dict = dict(tx)
                # Convert date for JSON
                if tx_dict['date']:
                    tx_dict['date'] = str(tx_dict['date'])
                transactions_list.append(tx_dict)
            
            return jsonify({
                "success": True,
                "transactions": transactions_list,
                "total_shown": len(transactions_list)
            })
        except Exception as e:
            logger.error(f"Admin transactions fetch failed: {e}")
            return jsonify({"error": "Failed to fetch transactions"}), 500

    @app.route('/admin/analytics', methods=['GET'])
    @jwt_required()
    def admin_get_analytics():
        """Get system analytics (admin only) - EXCLUDES ADMIN DATA"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            # 🆕 UPDATED: All analytics exclude admin user and their data
            
            # User statistics (exclude admin user)
            total_users = db.query_db(
                "SELECT COUNT(*) as count FROM users WHERE email != 'admin@budgetwise.com'",  # 🆕 CHANGED
                one=True
            )['count']
            
            active_users = db.query_db(
                "SELECT COUNT(DISTINCT user_id) as count FROM transactions WHERE date >= date('now', '-30 days') AND user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')",  # 🆕 CHANGED
                one=True
            )['count']
            
            # Transaction statistics (exclude admin transactions)
            total_transactions = db.query_db(
                "SELECT COUNT(*) as count FROM transactions WHERE user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')",  # 🆕 CHANGED
                one=True
            )['count']
            
            transactions_today = db.query_db(
                "SELECT COUNT(*) as count FROM transactions WHERE date = date('now') AND user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')",  # 🆕 CHANGED
                one=True
            )['count']
            
            # Category statistics (exclude admin transactions)
            popular_categories = db.query_db('''
                SELECT category, COUNT(*) as count 
                FROM transactions 
                WHERE type = 'expense' AND user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')  -- 🆕 CHANGED
                GROUP BY category 
                ORDER BY count DESC 
                LIMIT 5
            ''')
            
            # Goal statistics (exclude admin goals)
            total_goals = db.query_db(
                "SELECT COUNT(*) as count FROM financial_goals WHERE user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')",  # 🆕 CHANGED
                one=True
            )['count']
            
            completed_goals = db.query_db(
                "SELECT COUNT(*) as count FROM financial_goals WHERE current_amount >= target_amount AND user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')",  # 🆕 CHANGED
                one=True
            )['count']
            
            return jsonify({
                "success": True,
                "analytics": {
                    "users": {
                        "total": total_users,
                        "active_last_30_days": active_users,
                        "inactive": total_users - active_users
                    },
                    "transactions": {
                        "total": total_transactions,
                        "today": transactions_today,
                        "avg_per_user": round(total_transactions / max(total_users, 1), 2)
                    },
                    "goals": {
                        "total": total_goals,
                        "completed": completed_goals,
                        "completion_rate": round((completed_goals / max(total_goals, 1)) * 100, 2)
                    },
                    "popular_categories": [dict(cat) for cat in popular_categories],
                    "system": {
                        "database_size": "N/A",
                        "last_updated": datetime.now().isoformat()
                    }
                }
            })
        except Exception as e:
            logger.error(f"Admin analytics fetch failed: {e}")
            return jsonify({"error": "Failed to fetch analytics"}), 500

    # 🆕 NEW: Category Management Endpoints
    @app.route('/admin/categories', methods=['GET'])
    @jwt_required()
    def admin_get_categories():
        """Get all categories and their usage statistics"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            # Get category usage statistics
            categories = db.query_db('''
                SELECT 
                    category,
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount,
                    COUNT(DISTINCT user_id) as unique_users,
                    MIN(date) as first_used,
                    MAX(date) as last_used
                FROM transactions 
                WHERE user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')  -- 🆕 CHANGED
                GROUP BY category
                ORDER BY transaction_count DESC
            ''')
            
            categories_list = []
            for cat in categories:
                cat_dict = dict(cat)
                # Convert dates to string
                if cat_dict['first_used']:
                    cat_dict['first_used'] = str(cat_dict['first_used'])
                if cat_dict['last_used']:
                    cat_dict['last_used'] = str(cat_dict['last_used'])
                categories_list.append(cat_dict)
            
            return jsonify({
                "success": True,
                "categories": categories_list,
                "total_categories": len(categories_list)
            })
        except Exception as e:
            logger.error(f"Admin categories fetch failed: {e}")
            return jsonify({"error": "Failed to fetch categories"}), 500

    @app.route('/admin/categories/update', methods=['POST'])
    @jwt_required()
    def admin_update_categories():
        """Update transaction categories in bulk"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            data = request.get_json(force=True)
            old_category = data.get('old_category')
            new_category = data.get('new_category')
            
            if not old_category or not new_category:
                return jsonify({"error": "Both old_category and new_category are required"}), 400
            
            # Update transactions with the old category
            updated_count = db.execute_db(
                "UPDATE transactions SET category = ? WHERE category = ? AND user_id IN (SELECT id FROM users WHERE email != 'admin@budgetwise.com')",  # 🆕 CHANGED
                (new_category, old_category)
            )
            
            logger.info(f"Admin {user_id} updated {updated_count} transactions from '{old_category}' to '{new_category}'")
            
            return jsonify({
                "success": True,
                "message": f"Updated {updated_count} transactions from '{old_category}' to '{new_category}'",
                "updated_count": updated_count
            })
        except Exception as e:
            logger.error(f"Admin category update failed: {e}")
            return jsonify({"error": "Failed to update categories"}), 500

    # 🆕 NEW: System Monitoring Endpoints

    @app.route('/admin/system/health', methods=['GET'])
    @jwt_required()
    def admin_system_health():
        """Get system health and data consistency checks"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            health_checks = {}
            
            # Database size check
            try:
                db_size = db.query_db("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()", one=True)
                health_checks['database_size'] = f"{db_size['size'] / (1024*1024):.2f} MB"
            except:
                health_checks['database_size'] = "Unknown"
            
            # Table row counts
            tables = ['users', 'transactions', 'financial_goals']  # 🆕 REMOVED: admin_users
            for table in tables:
                try:
                    count = db.query_db(f"SELECT COUNT(*) as count FROM {table}", one=True)
                    health_checks[f'{table}_count'] = count['count']
                except:
                    health_checks[f'{table}_count'] = "Error"
            
            # Data consistency checks
            try:
                # Check for transactions without users
                orphaned_transactions = db.query_db(
                    "SELECT COUNT(*) as count FROM transactions WHERE user_id NOT IN (SELECT id FROM users)",
                    one=True
                )
                health_checks['orphaned_transactions'] = orphaned_transactions['count']
                
                # Check for goals without users
                orphaned_goals = db.query_db(
                    "SELECT COUNT(*) as count FROM financial_goals WHERE user_id NOT IN (SELECT id FROM users)",
                    one=True
                )
                health_checks['orphaned_goals'] = orphaned_goals['count']
            except:
                health_checks['data_consistency'] = "Check failed"
            
            # Recent errors from logs (simulated)
            health_checks['recent_errors'] = 0
            health_checks['system_status'] = "Healthy"
            
            # Performance metrics
            health_checks['server_uptime'] = "N/A"
            health_checks['last_backup'] = "Not implemented"
            
            return jsonify({
                "success": True,
                "health_checks": health_checks,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Admin system health check failed: {e}")
            return jsonify({"error": "Failed to check system health"}), 500

    @app.route('/admin/system/cleanup', methods=['POST'])
    @jwt_required()
    def admin_system_cleanup():
        """Perform system cleanup tasks"""
        user_id = int(get_jwt_identity())
        if not is_admin_user(user_id):
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            data = request.get_json(force=True) or {}
            cleanup_type = data.get('type', 'all')
            
            cleanup_results = {}
            
            if cleanup_type in ['orphaned', 'all']:
                # Clean up orphaned transactions
                orphaned_tx = db.execute_db(
                    "DELETE FROM transactions WHERE user_id NOT IN (SELECT id FROM users)"
                )
                cleanup_results['orphaned_transactions_removed'] = orphaned_tx
                
                # Clean up orphaned goals
                orphaned_goals = db.execute_db(
                    "DELETE FROM financial_goals WHERE user_id NOT IN (SELECT id FROM users)"
                )
                cleanup_results['orphaned_goals_removed'] = orphaned_goals
            
            if cleanup_type in ['test_data', 'all']:
                # Optional: Clean up test data (you can customize this)
                test_users = db.execute_db(
                    "DELETE FROM users WHERE email LIKE '%test%' OR email LIKE '%example%'"
                )
                cleanup_results['test_users_removed'] = test_users
            
            logger.info(f"Admin {user_id} performed system cleanup: {cleanup_results}")
            
            return jsonify({
                "success": True,
                "message": "System cleanup completed",
                "cleanup_results": cleanup_results
            })
        except Exception as e:
            logger.error(f"Admin system cleanup failed: {e}")
            return jsonify({"error": "Failed to perform system cleanup"}), 500

    @app.route('/admin/promote-to-admin', methods=['POST'])
    @jwt_required()
    def admin_promote_user():
        pass

    # ---------------- Debug Endpoints ----------------
    @app.route('/debug/goals', methods=['GET'])
    @jwt_required()
    def debug_goals():
        user_id = int(get_jwt_identity())
        
        # Check if goals table exists and has data
        try:
            goals = db.query_db("SELECT * FROM financial_goals WHERE user_id=?", (user_id,))
            goals_list = [dict(goal) for goal in goals]
            
            # Check table structure
            table_info = db.query_db("PRAGMA table_info(financial_goals)")
            
            return jsonify({
                "user_id": user_id,
                "goals_count": len(goals_list),
                "goals": goals_list,
                "table_structure": [dict(info) for info in table_info]
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # ---------------- AI Categorization Testing ----------------
    @app.route('/categorize/test', methods=['POST'])
    @jwt_required()
    def test_categorization():
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True)
        description = data.get('description', '').strip()
        
        if not description:
            return jsonify({"error": "Description required"}), 400
        
        try:
            category, confidence, suggestions = categorize(description)
            return jsonify({
                "description": description,
                "category": category,
                "confidence": confidence,
                "suggestions": suggestions,
                "normalized_category": normalize_category(category),
                "success": True
            })
        except Exception as e:
            return jsonify({
                "description": description,
                "category": "Uncategorized",
                "confidence": "low",
                "suggestions": ["Shopping", "Miscellaneous"],
                "error": str(e),
                "success": False
            }), 500
    
    return app

# ---------------- Run ----------------
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)