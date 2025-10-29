# backend/models.py
# lightweight model classes (not DB-bound ORM)
class User:
    def __init__(self, id, email, password_hash, created_at=None):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at

class Transaction:
    def __init__(self, id, user_id, date, amount, description=None, category=None, type='expense', created_at=None):
        self.id = id
        self.user_id = user_id
        self.date = date
        self.amount = amount
        self.description = description
        self.category = category
        self.type = type
        self.created_at = created_at
