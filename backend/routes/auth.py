from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import db, User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()

    required_fields = ['name', 'email', 'password', 'role']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Заполните все поля: name, email, password, role'}), 400

    if data['role'] not in ('master', 'student', 'company'):
        return jsonify({'error': 'role должен быть master, student или company'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Пользователь с таким email уже существует'}), 409

    user = User(
        name=data['name'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        role=data['role'],
    )
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id), additional_claims={'role': user.role})
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    email = data.get('login') or data.get('email')
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'ok': False, 'message': 'Неверный логин или пароль'}), 401

    token = create_access_token(identity=str(user.id), additional_claims={'role': user.role})
    return jsonify({
        'ok': True,
        'message': 'Успешный вход',
        'token': token,
        'user': user.to_dict(),
    }), 200