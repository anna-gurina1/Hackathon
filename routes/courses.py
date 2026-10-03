from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import db, Course

courses_bp = Blueprint('courses', __name__)


@courses_bp.route('/api/courses', methods=['POST'])
@jwt_required()
def create_course():
    """Создать курс. Доступно только мастеру."""
    claims = get_jwt()
    if claims.get('role') != 'master':
        return jsonify({'error': 'Создавать курсы может только мастер'}), 403

    data = request.get_json()
    if not data.get('title'):
        return jsonify({'error': 'Укажите title курса'}), 400

    course = Course(
        title=data['title'],
        description=data.get('description', ''),
        master_id=int(get_jwt_identity()),
        is_private=data.get('is_private', False),
        company_id=data.get('company_id'),
    )
    db.session.add(course)
    db.session.commit()
    return jsonify(course.to_dict()), 201


@courses_bp.route('/api/courses', methods=['GET'])
@jwt_required(optional=True)
def list_courses():
    """
    Список курсов.
    Обычным пользователям видны только публичные курсы.
    Сотруднику компании видны ещё и приватные курсы его компании (передай ?company_id=).
    """
    company_id = request.args.get('company_id', type=int)

    query = Course.query.filter_by(is_private=False)
    courses = query.all()

    if company_id:
        private_courses = Course.query.filter_by(is_private=True, company_id=company_id).all()
        courses += private_courses

    return jsonify([c.to_dict() for c in courses])


@courses_bp.route('/api/courses/<int:course_id>', methods=['GET'])
def get_course(course_id):
    """Детали курса вместе со всеми уроками и вопросами (без правильных ответов)."""
    course = Course.query.get_or_404(course_id)
    return jsonify(course.to_dict(include_lessons=True))