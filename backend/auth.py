# backend/auth.py
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(force=True)
    email = data.get('email')
    pwd = data.get('password')
    if not email or not pwd:
        return jsonify({"msg": "email and password required"}), 400

    existing = db.query_db("SELECT * FROM users WHERE email=?", (email,), one=True)
    if existing:
        return jsonify({"msg": "user exists"}), 400

    pwd_hash = generate_password_hash(pwd)
    user_id = db.execute_db(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, pwd_hash)
    )
    return jsonify({"msg": "registered", "user_id": user_id}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    email = data.get('email')
    pwd = data.get('password')
    if not email or not pwd:
        return jsonify({"msg": "email and password required"}), 400

    user = db.query_db("SELECT * FROM users WHERE email=?", (email,), one=True)
    if not user:
        return jsonify({"msg": "bad credentials"}), 401

    if not check_password_hash(user['password_hash'], pwd):
        return jsonify({"msg": "bad credentials"}), 401

    # IMPORTANT: cast identity to string so JWT subject ('sub') is a string
    access = create_access_token(identity=str(user['id']))
    return jsonify({
        "access_token": access,
        "user_id": user['id'],
        "email": user['email']
    })
