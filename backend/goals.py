# backend/goals.py
import sqlite3
from datetime import datetime, timedelta
import logging
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("expense-backend")

# Define DB_PATH at the top level
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "expense.db"))

class HumanGoalCoach:
    """Human-like AI Goal Achievement Coach - Provides REALISTIC financial advice"""
    
    def analyze_financial_situation(self, transactions_df: pd.DataFrame, goal: Dict) -> Dict[str, Any]:
        """Analyze current financial situation with HUMAN LOGIC"""
        if transactions_df.empty:
            return self._get_default_analysis(goal)
        
        try:
            # Ensure date is datetime
            if not transactions_df.empty and 'date' in transactions_df.columns:
                transactions_df['date'] = pd.to_datetime(transactions_df['date'], errors='coerce')
                transactions_df = transactions_df.dropna(subset=['date'])
            
            # Use last 3 months for current financial picture
            three_months_ago = datetime.now() - timedelta(days=90)
            recent_df = transactions_df[transactions_df['date'] >= three_months_ago].copy()
            
            if recent_df.empty:
                return self._get_default_analysis(goal)
            
            # Calculate REALISTIC monthly averages
            monthly_income = self._calculate_monthly_metric(recent_df, 'income')
            monthly_expenses = self._calculate_monthly_metric(recent_df, 'expense')
            
            # Current savings behavior (can be negative)
            current_monthly_savings = monthly_income - monthly_expenses
            
            # REALISTIC savings capacity (max 30% of income for aggressive saving)
            max_realistic_savings = monthly_income * 0.3  # 30% is aggressive but possible
            
            # Calculate goal requirements
            remaining_amount = max(0, goal['target_amount'] - goal.get('current_amount', 0))
            
            # Handle overdue goals - FIXED LOGIC
            days_remaining = goal.get('days_remaining', 0)
            is_overdue = days_remaining <= 0
            
            if is_overdue:
                # Goal is overdue - suggest new timeline
                days_remaining = 180  # 6 months extension
            
            monthly_savings_needed = self._calculate_monthly_savings_needed(remaining_amount, days_remaining)
            
            # Category analysis for SMART recommendations
            category_analysis = self._analyze_spending_categories(recent_df)
            
            return {
                'monthly_income': float(monthly_income),
                'monthly_expenses': float(monthly_expenses),
                'current_monthly_savings': float(current_monthly_savings),
                'max_realistic_savings': float(max_realistic_savings),
                'category_spending': category_analysis.get('category_details', {}),
                'monthly_savings_needed': float(monthly_savings_needed),
                'remaining_amount': float(remaining_amount),
                'feasibility_score': self._calculate_realistic_feasibility(monthly_savings_needed, max_realistic_savings, monthly_income),
                'top_spending_categories': self._get_top_spending_categories(category_analysis),
                'goal_size_ratio': goal['target_amount'] / monthly_income if monthly_income > 0 else 999,
                'is_overdue': is_overdue
            }
        except Exception as e:
            logger.error(f"Error in financial analysis: {str(e)}")
            return self._get_default_analysis(goal)
    
    def _analyze_spending_categories(self, df: pd.DataFrame) -> Dict:
        """Analyze spending categories with human logic"""
        if df.empty:
            return {'category_details': {}, 'optimization_opportunities': []}
        
        expense_df = df[df['type'] == 'expense']
        if expense_df.empty:
            return {'category_details': {}, 'optimization_opportunities': []}
        
        category_totals = expense_df.groupby('category')['amount'].sum()
        total_expenses = category_totals.sum()
        
        # Categorize spending types
        essential_categories = {'Rent', 'Utilities', 'Healthcare', 'Insurance', 'Loan_Repayment'}
        discretionary_categories = {'Entertainment', 'Dining', 'Shopping', 'Travel', 'Miscellaneous'}
        flexible_categories = {'Groceries', 'Transport', 'Education'}
        
        analysis = {
            'essential_spending': 0,
            'discretionary_spending': 0,
            'flexible_spending': 0,
            'category_details': {},
            'optimization_opportunities': []
        }
        
        for category, amount in category_totals.items():
            percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
            
            category_info = {
                'amount': float(amount),
                'percentage': round(percentage, 1),
                'type': 'unknown'
            }
            
            if category in essential_categories:
                category_info['type'] = 'essential'
                analysis['essential_spending'] += amount
            elif category in discretionary_categories:
                category_info['type'] = 'discretionary'
                analysis['discretionary_spending'] += amount
            elif category in flexible_categories:
                category_info['type'] = 'flexible'
                analysis['flexible_spending'] += amount
            
            analysis['category_details'][category] = category_info
        
        # Find optimization opportunities
        analysis['optimization_opportunities'] = self._find_optimization_opportunities(analysis)
        
        return analysis
    
    def _find_optimization_opportunities(self, analysis: Dict) -> List[Dict]:
        """Find realistic optimization opportunities"""
        opportunities = []
        category_details = analysis.get('category_details', {})
        
        # Benchmark percentages (typical spending patterns)
        benchmarks = {
            'Groceries': 15,      # 10-15% typical
            'Entertainment': 5,    # 3-7% typical  
            'Dining': 7,          # 5-10% typical
            'Shopping': 5,         # 3-8% typical
            'Transport': 10,       # 8-12% typical
        }
        
        total_spending = analysis.get('essential_spending', 0) + \
                        analysis.get('discretionary_spending', 0) + \
                        analysis.get('flexible_spending', 0)
        
        for category, details in category_details.items():
            if total_spending == 0:
                continue
                
            current_percentage = details['percentage']
            benchmark = benchmarks.get(category)
            
            # Only suggest reductions for discretionary and flexible spending
            if details['type'] in ['discretionary', 'flexible'] and benchmark and current_percentage > benchmark * 1.5:
                excess_amount = (current_percentage - benchmark) / 100 * total_spending
                if excess_amount > 1000:  # Only suggest if meaningful amount
                    opportunities.append({
                        'category': category,
                        'current_percentage': current_percentage,
                        'benchmark_percentage': benchmark,
                        'excess_amount': excess_amount,
                        'suggested_reduction': excess_amount * 0.3,  # Suggest 30% of excess
                        'reason': f"Spending on {category} is {current_percentage:.1f}% of budget (typical: {benchmark}%)"
                    })
        
        # Sort by potential savings
        opportunities.sort(key=lambda x: x['suggested_reduction'], reverse=True)
        return opportunities[:3]  # Return top 3
    
    def _get_top_spending_categories(self, analysis: Dict) -> List[str]:
        """Get top 3 spending categories"""
        category_details = analysis.get('category_details', {})
        if not category_details:
            return []
        
        # Sort by amount spent
        sorted_categories = sorted(category_details.items(), key=lambda x: x[1]['amount'], reverse=True)
        return [category for category, details in sorted_categories[:3]]
    
    def generate_action_plan(self, analysis: Dict, goal: Dict) -> Dict[str, Any]:
        """Generate REALISTIC human-like action plan"""
        
        monthly_needed = analysis['monthly_savings_needed']
        max_savings = analysis['max_realistic_savings']
        current_savings = analysis['current_monthly_savings']
        monthly_income = analysis['monthly_income']
        is_overdue = analysis.get('is_overdue', False)
        
        # Calculate REALISTIC success probability
        success_probability = self._calculate_human_success_probability(analysis, goal)
        
        # Generate HUMAN-LIKE recommendations
        recommendations = self._generate_human_recommendations(analysis, monthly_needed, max_savings)
        
        # Generate action steps with HUMAN LOGIC
        action_steps = self._generate_human_action_steps(analysis, goal, success_probability, is_overdue)
        
        # Calculate realistic timeline
        realistic_timeline = self._calculate_realistic_timeline(goal, analysis, success_probability)
        
        return {
            'monthly_savings_needed': monthly_needed,
            'current_monthly_savings': current_savings,
            'max_possible_savings': max_savings,
            'savings_gap': max(0, monthly_needed - current_savings),
            'recommendations': recommendations,
            'success_probability': success_probability,
            'estimated_completion_date': realistic_timeline['suggested_date'],
            'weekly_target': monthly_needed / 4,
            'action_steps': action_steps,
            'reality_check': self._get_human_reality_check(analysis, goal)
        }
    
    def _calculate_human_success_probability(self, analysis: Dict, goal: Dict) -> float:
        """Calculate success probability with HUMAN LOGIC"""
        monthly_needed = analysis['monthly_savings_needed']
        max_savings = analysis['max_realistic_savings']
        current_savings = analysis['current_monthly_savings']
        monthly_income = analysis['monthly_income']
        
        # If goal is already achieved
        if goal.get('current_amount', 0) >= goal['target_amount']:
            return 100.0
        
        # If goal is overdue
        if analysis.get('is_overdue', False):
            return 10.0  # Very low probability for overdue goals
        
        # Calculate what percentage of income is needed
        income_percentage_needed = (monthly_needed / monthly_income * 100) if monthly_income > 0 else 100
        
        # Human logic: 
        # - 0-10% of income: Easy (90% probability)
        # - 10-20%: Moderate (70% probability)  
        # - 20-30%: Challenging (50% probability)
        # - 30-50%: Difficult (30% probability)
        # - 50%+: Very difficult (10% probability)
        
        if income_percentage_needed <= 10:
            base_prob = 90.0
        elif income_percentage_needed <= 20:
            base_prob = 70.0
        elif income_percentage_needed <= 30:
            base_prob = 50.0
        elif income_percentage_needed <= 50:
            base_prob = 30.0
        else:
            base_prob = 10.0
        
        # Adjust based on current savings behavior
        if current_savings >= monthly_needed:
            behavior_boost = 20.0  # Already saving enough
        elif current_savings >= monthly_needed * 0.5:
            behavior_boost = 10.0  # Halfway there
        elif current_savings > 0:
            behavior_boost = 5.0   # Some savings habit
        else:
            behavior_boost = 0.0   # No savings habit
        
        probability = max(5, min(95, base_prob + behavior_boost))
        return round(probability, 1)
    
    def _generate_human_recommendations(self, analysis: Dict, monthly_needed: float, max_savings: float) -> List[Dict]:
        """Generate recommendations that are ACTUALLY POSSIBLE"""
        recommendations = []
        category_analysis = analysis.get('category_analysis', {})
        optimization_opportunities = category_analysis.get('optimization_opportunities', [])
        monthly_income = analysis['monthly_income']
        
        total_potential_savings = 0
        
        # First, suggest from optimization opportunities
        for opportunity in optimization_opportunities:
            if total_potential_savings >= monthly_needed:
                break
                
            suggested_savings = opportunity['suggested_reduction']
            
            # Ensure suggestion is meaningful and realistic
            if suggested_savings > 100:  # At least ₹100 savings
                recommendations.append({
                    'category': opportunity['category'],
                    'current_spending': opportunity['excess_amount'] + (opportunity['benchmark_percentage'] / 100 * (analysis['monthly_income'] - analysis['monthly_expenses'])),
                    'suggested_reduction': suggested_savings,
                    'action': f"Review {opportunity['category']} spending",
                    'impact': f"Save ₹{suggested_savings:,.0f}/month"
                })
                total_potential_savings += suggested_savings
        
        # If still not enough, suggest income increase for unrealistic goals
        if monthly_needed > max_savings and monthly_income > 0:
            income_gap = monthly_needed - max_savings
            recommendations.append({
                'category': 'Income',
                'current_spending': 0,
                'suggested_reduction': 0,
                'action': f"Explore additional income sources",
                'impact': f"Need additional ₹{income_gap:,.0f}/month to meet goal"
            })
        
        # If no good recommendations, provide general advice
        if not recommendations:
            recommendations.append({
                'category': 'General',
                'current_spending': 0,
                'suggested_reduction': 0,
                'action': "Review overall budget and spending patterns",
                'impact': "Identify areas for improvement"
            })
        
        return recommendations[:3]  # Return top 3 most impactful
    
    def _generate_human_action_steps(self, analysis: Dict, goal: Dict, success_prob: float, is_overdue: bool) -> List[str]:
        """Generate practical, human-like action steps"""
        action_steps = []
        monthly_needed = analysis['monthly_savings_needed']
        current_savings = analysis['current_monthly_savings']
        max_savings = analysis['max_realistic_savings']
        
        # Header
        action_steps.append(f"🎯 **Goal:** {goal['goal_name']} - ₹{goal['target_amount']:,.0f}")
        action_steps.append(f"📊 **Monthly Target:** ₹{monthly_needed:,.0f}")
        
        # Progress if any
        if goal.get('current_amount', 0) > 0:
            progress = (goal['current_amount'] / goal['target_amount']) * 100
            action_steps.append(f"📈 **Current Progress:** {progress:.1f}% (₹{goal['current_amount']:,.0f})")
        
        # Overdue handling
        if is_overdue:
            action_steps.append("⏰ **STATUS: OVERDUE** - Let's create a new plan")
            action_steps.append("💡 **Suggestion:** Extend target date by 6 months")
        
        # Reality-based messaging
        if monthly_needed > max_savings * 1.5:
            action_steps.append("🚨 **Reality Check:** This goal requires significant lifestyle changes")
            action_steps.append(f"💰 **Current Capacity:** ₹{max_savings:,.0f}/month vs Needed: ₹{monthly_needed:,.0f}/month")
            action_steps.append("💡 **Consider:** Breaking goal into smaller milestones")
        elif monthly_needed > max_savings:
            action_steps.append("⚠️ **Challenge:** Goal exceeds current savings capacity")
            action_steps.append(f"📊 **Gap:** Additional ₹{monthly_needed - max_savings:,.0f}/month needed")
        elif current_savings >= monthly_needed:
            action_steps.append("✅ **Great!** You're already saving enough for this goal")
        elif current_savings > 0:
            gap = monthly_needed - current_savings
            action_steps.append(f"📈 **Progress:** You're saving ₹{current_savings:,.0f}/month")
            action_steps.append(f"🎯 **Need:** Additional ₹{gap:,.0f}/month")
        else:
            action_steps.append("🔰 **Starting Point:** Begin building savings habit")
            first_step_amount = min(monthly_needed, 1000)  # Start small
            action_steps.append(f"✨ **First Step:** Save ₹{first_step_amount:,.0f} this month")
        
        return action_steps
    
    def _get_human_reality_check(self, analysis: Dict, goal: Dict) -> List[str]:
        """Provide honest, human reality checks"""
        checks = []
        monthly_needed = analysis['monthly_savings_needed']
        max_savings = analysis['max_realistic_savings']
        goal_ratio = analysis['goal_size_ratio']
        monthly_income = analysis['monthly_income']
        
        # Savings capacity check
        savings_ratio = monthly_needed / monthly_income if monthly_income > 0 else 1
        if savings_ratio > 0.5:
            checks.append(f"💸 **Aggressive Saving:** This goal requires saving {savings_ratio:.0%} of your income")
            checks.append("💡 **Suggestion:** Consider a longer timeline or smaller goal")
        
        # Goal size check
        if goal_ratio > 12:
            checks.append(f"🏔️ **Large Goal:** This is {goal_ratio:.1f}x your monthly income")
            checks.append("🎯 **Recommendation:** Break into smaller 3-6 month milestones")
        elif goal_ratio > 6:
            checks.append(f"📏 **Substantial Goal:** This is {goal_ratio:.1f}x your monthly income")
        
        # Timeline check
        if analysis.get('is_overdue', False):
            checks.append("📅 **Timeline Adjustment:** Original deadline passed - setting new target")
        
        if analysis['current_monthly_savings'] <= 0:
            checks.append("💡 **Starting Point:** Focus on creating a basic savings habit first")
        
        return checks
    
    def _calculate_realistic_timeline(self, goal: Dict, analysis: Dict, success_prob: float) -> Dict:
        """Calculate realistic timeline with human logic"""
        try:
            original_date = datetime.strptime(goal['target_date'], '%Y-%m-%d').date()
            current_date = datetime.now().date()
            
            # If goal is overdue or low probability, suggest new timeline
            if analysis.get('is_overdue', False) or success_prob < 40:
                remaining_amount = analysis['remaining_amount']
                monthly_capacity = analysis['max_realistic_savings']
                
                if monthly_capacity > 0:
                    realistic_months = max(3, remaining_amount / monthly_capacity)  # Minimum 3 months
                    new_date = current_date + timedelta(days=realistic_months * 30)
                    return {
                        'original_date': goal['target_date'],
                        'suggested_date': new_date.strftime('%Y-%m-%d'),
                        'months_required': round(realistic_months, 1),
                        'reason': 'Adjusted for realistic savings capacity'
                    }
            
            return {
                'original_date': goal['target_date'],
                'suggested_date': goal['target_date'],
                'months_required': goal.get('days_remaining', 180) / 30,
                'reason': 'Current timeline appears realistic'
            }
        except:
            return {
                'original_date': goal['target_date'],
                'suggested_date': goal['target_date'],
                'months_required': 6,
                'reason': 'Using default timeline'
            }
    
    def _calculate_realistic_feasibility(self, monthly_needed: float, max_savings: float, monthly_income: float) -> float:
        """Calculate how feasible the goal is with human logic"""
        if monthly_needed <= 0:
            return 100.0
        
        if monthly_income == 0:
            return 0.0
        
        # Feasibility based on percentage of income and savings capacity
        income_percentage = (monthly_needed / monthly_income) * 100
        
        if monthly_needed <= max_savings * 0.5:
            feasibility = 90.0  # Easy
        elif monthly_needed <= max_savings:
            feasibility = 70.0  # Moderate
        elif monthly_needed <= max_savings * 1.5:
            feasibility = 40.0  # Difficult
        elif monthly_needed <= max_savings * 2:
            feasibility = 20.0  # Very difficult
        else:
            feasibility = 5.0   # Nearly impossible
        
        return round(feasibility, 1)
    
    def _calculate_monthly_metric(self, df: pd.DataFrame, transaction_type: str) -> float:
        """Calculate monthly average"""
        if df.empty:
            return 0.0
        
        type_df = df[df['type'] == transaction_type]
        if type_df.empty:
            return 0.0
        
        days_covered = max(30, (df['date'].max() - df['date'].min()).days)
        total_amount = type_df['amount'].sum()
        monthly_average = total_amount / (days_covered / 30.0)
        
        return max(0.0, monthly_average)
    
    def _calculate_monthly_savings_needed(self, remaining_amount: float, days_remaining: int) -> float:
        """Calculate monthly savings needed"""
        if days_remaining <= 0:
            # If overdue, assume 6 months extension for calculation
            months_remaining = 6
        else:
            months_remaining = max(1, days_remaining / 30.0)
            
        return remaining_amount / months_remaining
    
    def _get_default_analysis(self, goal: Dict) -> Dict[str, Any]:
        """Return default analysis"""
        remaining_amount = goal['target_amount'] - goal.get('current_amount', 0)
        monthly_savings_needed = self._calculate_monthly_savings_needed(remaining_amount, goal.get('days_remaining', 30))
        
        return {
            'monthly_income': 0,
            'monthly_expenses': 0,
            'current_monthly_savings': 0,
            'max_realistic_savings': 0,
            'category_spending': {},
            'monthly_savings_needed': float(monthly_savings_needed),
            'remaining_amount': float(remaining_amount),
            'feasibility_score': 30.0,
            'top_spending_categories': [],
            'goal_size_ratio': 999,
            'is_overdue': goal.get('days_remaining', 0) <= 0
        }

class GoalManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.coach = HumanGoalCoach()  # Use the human-like coach
    
    def create_goals_table(self):
        """Create goals table if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS financial_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    goal_name TEXT NOT NULL,
                    goal_type TEXT CHECK(goal_type IN ('savings', 'spending_reduction', 'category_budget')) NOT NULL,
                    target_amount DECIMAL(10,2) NOT NULL,
                    current_amount DECIMAL(10,2) DEFAULT 0,
                    target_date DATE NOT NULL,
                    category TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS goal_savings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id INTEGER NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    saved_date DATE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (goal_id) REFERENCES financial_goals(id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Goals tables created or already exist")
            return True
        except Exception as e:
            logger.error(f"Error creating goals tables: {str(e)}")
            return False
    
    def add_savings_to_goal(self, goal_id: int, amount: float, description: str = "") -> Tuple[bool, str]:
        """Add savings to a specific goal"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT target_amount, current_amount FROM financial_goals WHERE id = ?', (goal_id,))
            goal = cursor.fetchone()
            
            if not goal:
                return False, "Goal not found"
            
            target_amount, current_amount = goal
            
            if current_amount >= target_amount:
                return False, "Goal already achieved! Cannot add more savings."
            
            new_amount = current_amount + amount
            
            if new_amount > target_amount:
                amount = target_amount - current_amount
                new_amount = target_amount
            
            cursor.execute('''
                INSERT INTO goal_savings (goal_id, amount, saved_date, description)
                VALUES (?, ?, ?, ?)
            ''', (goal_id, float(amount), datetime.now().date().isoformat(), description))
            
            cursor.execute('''
                UPDATE financial_goals 
                SET current_amount = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (float(new_amount), goal_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added ₹{amount} to goal {goal_id}")
            return True, f"Added ₹{amount} to goal. New total: ₹{new_amount}"
            
        except Exception as e:
            logger.error(f"Error adding savings to goal: {str(e)}")
            return False, str(e)
    
    def get_goal_savings_history(self, goal_id: int):
        """Get savings history for a goal"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM goal_savings 
                WHERE goal_id = ? 
                ORDER BY saved_date DESC
            ''', (goal_id,))
            
            savings = []
            for row in cursor.fetchall():
                savings.append({
                    'id': row[0],
                    'goal_id': row[1],
                    'amount': float(row[2]),
                    'saved_date': row[3],
                    'description': row[4],
                    'created_at': row[5]
                })
            
            conn.close()
            return savings, None
            
        except Exception as e:
            logger.error(f"Error getting goal savings: {str(e)}")
            return None, str(e)
    
    def get_user_goals(self, user_id):
        """Get all goals for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM financial_goals 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (user_id,))
            
            goals = []
            for row in cursor.fetchall():
                goal = {
                    'id': row[0],
                    'user_id': row[1],
                    'goal_name': row[2],
                    'goal_type': row[3],
                    'target_amount': float(row[4]),
                    'current_amount': float(row[5]),
                    'target_date': row[6],
                    'category': row[7],
                    'description': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                }
                
                if goal['target_amount'] > 0:
                    goal['progress_percent'] = min(100, (goal['current_amount'] / goal['target_amount']) * 100)
                else:
                    goal['progress_percent'] = 0
                
                try:
                    target_date = datetime.strptime(goal['target_date'], '%Y-%m-%d').date()
                    days_remaining = (target_date - datetime.now().date()).days
                    goal['days_remaining'] = max(0, days_remaining)
                except:
                    goal['days_remaining'] = 30
                
                if goal['progress_percent'] >= 100:
                    goal['status'] = 'achieved'
                elif goal['days_remaining'] <= 0:
                    goal['status'] = 'overdue'
                else:
                    goal['status'] = 'active'
                
                goals.append(goal)
            
            conn.close()
            return goals, None
            
        except Exception as e:
            logger.error(f"Error getting user goals: {str(e)}")
            return None, str(e)
    
    def calculate_goal_progress(self, user_id, transactions_data):
        """Calculate progress for all goals"""
        try:
            goals, error = self.get_user_goals(user_id)
            if error:
                return None, error
            
            return goals, None
            
        except Exception as e:
            logger.error(f"Error calculating goal progress: {str(e)}")
            return None, str(e)
    
    def get_goal_coaching(self, user_id, goal_id, transactions_data):
        """Get AI coaching for a specific goal using HUMAN LOGIC"""
        try:
            goals, error = self.get_user_goals(user_id)
            if error:
                return None, error
            
            goal = next((g for g in goals if g['id'] == goal_id), None)
            if not goal:
                return None, "Goal not found"
            
            if isinstance(transactions_data, list):
                transactions_df = pd.DataFrame(transactions_data)
            else:
                transactions_df = transactions_data
            
            if not transactions_df.empty:
                if 'date' in transactions_df.columns:
                    transactions_df['date'] = pd.to_datetime(transactions_df['date'], errors='coerce')
                if 'type' in transactions_df.columns:
                    transactions_df['type'] = transactions_df['type'].str.lower().str.strip()
                if 'amount' in transactions_df.columns:
                    transactions_df['amount'] = pd.to_numeric(transactions_df['amount'], errors='coerce')
            
            financial_analysis = self.coach.analyze_financial_situation(transactions_df, goal)
            action_plan = self.coach.generate_action_plan(financial_analysis, goal)
            savings_history, _ = self.get_goal_savings_history(goal_id)
            
            coaching_result = {
                'goal': goal,
                'financial_analysis': financial_analysis,
                'action_plan': action_plan,
                'savings_history': savings_history,
                'coaching_tips': self._get_human_coaching_tips(goal, action_plan['success_probability'])
            }
            
            return coaching_result, None
            
        except Exception as e:
            logger.error(f"Error generating goal coaching: {str(e)}")
            return None, str(e)
    
    def _get_human_coaching_tips(self, goal: Dict, success_prob: float) -> List[str]:
        """Get human-like coaching tips"""
        tips = []
        
        if success_prob >= 80:
            tips.append("🎉 **You're on track!** Keep up the consistent savings habit")
        elif success_prob >= 60:
            tips.append("📈 **Good progress** - a few small adjustments could increase your success rate")
        elif success_prob >= 40:
            tips.append("⚠️ **This will be challenging** - consider extending your timeline")
        else:
            tips.append("🔴 **Major adjustments needed** - this goal may not be realistic right now")
        
        if goal.get('current_amount', 0) > 0:
            tips.append("💪 **Momentum matters** - regular contributions build powerful habits")
        
        if goal['days_remaining'] < 30:
            tips.append("⏰ **Final stretch** - stay focused for the last few weeks!")
        
        tips.append("✅ **Weekly check-ins** help maintain momentum and adjust as needed")
        
        return tips
    
    def create_goal(self, user_id, goal_data):
        """Create a new financial goal"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            required_fields = ['goal_name', 'goal_type', 'target_amount', 'target_date']
            for field in required_fields:
                if field not in goal_data:
                    return None, f"Missing required field: {field}"
            
            try:
                target_date = datetime.strptime(goal_data['target_date'], '%Y-%m-%d').date()
                if target_date <= datetime.now().date():
                    goal_data['target_date'] = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            except:
                goal_data['target_date'] = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                INSERT INTO financial_goals 
                (user_id, goal_name, goal_type, target_amount, current_amount, target_date, category, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                goal_data['goal_name'],
                goal_data['goal_type'],
                float(goal_data['target_amount']),
                float(goal_data.get('current_amount', 0)),
                goal_data['target_date'],
                goal_data.get('category'),
                goal_data.get('description', '')
            ))
            
            goal_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Goal created successfully: ID {goal_id}")
            return goal_id, None
            
        except Exception as e:
            logger.error(f"Error creating goal: {str(e)}")
            return None, str(e)
    
    def delete_goal(self, goal_id, user_id):
        """Delete a goal"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM financial_goals 
                WHERE id = ? AND user_id = ?
            ''', (goal_id, user_id))
            
            affected_rows = cursor.rowcount
            conn.commit()
            conn.close()
            
            if affected_rows == 0:
                return False, "Goal not found or access denied"
            
            logger.info(f"Goal {goal_id} deleted successfully")
            return True, None
            
        except Exception as e:
            logger.error(f"Error deleting goal: {str(e)}")
            return False, str(e)
    
    def get_goal_analytics(self, user_id):
        """Get analytics for all user goals"""
        try:
            goals, error = self.get_user_goals(user_id)
            if error:
                return None, error
            
            analytics = {
                'total_goals': len(goals),
                'completed_goals': len([g for g in goals if g['progress_percent'] >= 100]),
                'in_progress_goals': len([g for g in goals if 0 < g['progress_percent'] < 100]),
                'not_started_goals': len([g for g in goals if g['progress_percent'] == 0]),
                'overdue_goals': len([g for g in goals if g.get('status') == 'overdue']),
                'total_target_amount': sum(g['target_amount'] for g in goals),
                'total_current_amount': sum(g['current_amount'] for g in goals),
                'goals_by_type': {},
                'upcoming_deadlines': [],
                'overdue_goals_list': []
            }
            
            for goal in goals:
                goal_type = goal['goal_type']
                if goal_type not in analytics['goals_by_type']:
                    analytics['goals_by_type'][goal_type] = 0
                analytics['goals_by_type'][goal_type] += 1
            
            thirty_days_later = datetime.now().date() + timedelta(days=30)
            for goal in goals:
                try:
                    target_date = datetime.strptime(goal['target_date'], '%Y-%m-%d').date()
                    current_date = datetime.now().date()
                    
                    if target_date < current_date and goal['progress_percent'] < 100:
                        analytics['overdue_goals_list'].append({
                            'goal_name': goal['goal_name'],
                            'target_date': goal['target_date'],
                            'days_overdue': (current_date - target_date).days,
                            'progress_percent': goal['progress_percent']
                        })
                    elif current_date <= target_date <= thirty_days_later:
                        analytics['upcoming_deadlines'].append({
                            'goal_name': goal['goal_name'],
                            'target_date': goal['target_date'],
                            'days_remaining': goal['days_remaining'],
                            'progress_percent': goal['progress_percent']
                        })
                except:
                    continue
            
            return analytics, None
            
        except Exception as e:
            logger.error(f"Error getting goal analytics: {str(e)}")
            return None, str(e)

# Global instance for easy import
goal_manager = GoalManager()