from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from models import db, Enrollment, CourseLog, Question, Lesson, Course

enrollment_bp = Blueprint('enrollment', __name__)


@enrollment_bp.route('/api/log', methods=['POST'])
@jwt_required()
def log_action():
    """
    Записать любое действие сотрудника: начал урок, ответил на вопрос и т.д.
    Это и есть те самые "логи", по которым потом видно полную историю прохождения.
    """
    data = request.get_json()
    log = CourseLog(
        student_id=int(get_jwt_identity()),
        course_id=data['course_id'],
        lesson_id=data.get('lesson_id'),
        action=data['action'],  # например 'started_lesson' / 'answered_question'
        details=data.get('details'),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(log.to_dict()), 201


@enrollment_bp.route('/api/courses/<int:course_id>/submit', methods=['POST'])
@jwt_required()
def submit_test(course_id):
    """
    Финальная сдача теста по курсу.
    Принимает answers = { question_id: "выбранный вариант" }.
    Считает процент правильных, сохраняет Enrollment, пишет лог завершения.
    """
    student_id = int(get_jwt_identity())
    data = request.get_json()
    answers = data.get('answers', {})

    # Собираем все вопросы всех уроков этого курса
    lessons = Lesson.query.filter_by(course_id=course_id).all()
    all_questions = [q for lesson in lessons for q in lesson.questions]

    if not all_questions:
        return jsonify({'error': 'В курсе нет вопросов'}), 400

    correct_count = sum(
        1 for q in all_questions
        if answers.get(str(q.id)) == q.correct_answer
    )
    score = round((correct_count / len(all_questions)) * 100)

    enrollment = Enrollment.query.filter_by(
        student_id=student_id, course_id=course_id
    ).first()
    if not enrollment:
        enrollment = Enrollment(student_id=student_id, course_id=course_id)
        db.session.add(enrollment)

    enrollment.score = score
    # Порог прохождения 70% — поменяйте под свои правила
    PASS_THRESHOLD = 70
    if score >= PASS_THRESHOLD:
        enrollment.status = 'completed'
        enrollment.completed_at = datetime.utcnow()

    db.session.commit()

    # Лог завершения — компания потом увидит это в истории
    db.session.add(CourseLog(
        student_id=student_id,
        course_id=course_id,
        action='completed_course' if enrollment.status == 'completed' else 'failed_test',
        details=f'score={score}',
    ))
    db.session.commit()

    return jsonify({
        'score': score,
        'status': enrollment.status,
        'passed': enrollment.status == 'completed',
    })


@enrollment_bp.route('/api/companies/<int:company_id>/graduates', methods=['GET'])
@jwt_required()
def get_graduates(company_id):
    """
    'Уведомление компании' в упрощённом виде для хакатона:
    компания просто запрашивает список сотрудников, завершивших её курсы.
    На проде это можно заменить на реальную рассылку (email/webhook).
    """
    company_courses = Course.query.filter_by(company_id=company_id).all()
    course_ids = [c.id for c in company_courses]

    completed = Enrollment.query.filter(
        Enrollment.course_id.in_(course_ids),
        Enrollment.status == 'completed'
    ).all()

    return jsonify([e.to_dict() for e in completed])


@enrollment_bp.route('/api/students/<int:student_id>/logs', methods=['GET'])
@jwt_required()
def get_student_logs(student_id):
    """Полная история действий конкретного сотрудника — для проверки компанией."""
    logs = CourseLog.query.filter_by(student_id=student_id).order_by(CourseLog.timestamp).all()
    return jsonify([l.to_dict() for l in logs])