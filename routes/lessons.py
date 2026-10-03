import json
import cloudinary.uploader
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from models import db, Lesson, Question, Course

lessons_bp = Blueprint('lessons', __name__)


def _check_is_master():
    claims = get_jwt()
    return claims.get('role') == 'master'


@lessons_bp.route('/api/lessons/video', methods=['POST'])
@jwt_required()
def upload_video_lesson():
    """
    Загрузка видео-урока.
    Ожидает multipart/form-data: file (видео), course_id, title, order.
    Видео физически улетает в Cloudinary, в базе хранится только ссылка.
    """
    if not _check_is_master():
        return jsonify({'error': 'Добавлять уроки может только мастер'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Прикрепите видеофайл в поле file'}), 400

    file = request.files['file']
    course_id = request.form.get('course_id', type=int)
    title = request.form.get('title', 'Видео-урок')
    order = request.form.get('order', 0, type=int)

    if not course_id or not Course.query.get(course_id):
        return jsonify({'error': 'Курс не найден'}), 404

    # resource_type='video' обязателен для Cloudinary, иначе загрузит как картинку
    upload_result = cloudinary.uploader.upload(
        file,
        resource_type='video',
        folder='course_videos',
    )

    lesson = Lesson(
        course_id=course_id,
        type='video',
        title=title,
        order=order,
        video_url=upload_result['secure_url'],
        video_public_id=upload_result['public_id'],
    )
    db.session.add(lesson)
    db.session.commit()

    return jsonify(lesson.to_dict()), 201


@lessons_bp.route('/api/lessons/text', methods=['POST'])
@jwt_required()
def create_text_lesson():
    """Создание текстового урока (лекции) — просто текст, без файлов."""
    if not _check_is_master():
        return jsonify({'error': 'Добавлять уроки может только мастер'}), 403

    data = request.get_json()
    required = ['course_id', 'text_content']
    if not all(f in data for f in required):
        return jsonify({'error': 'Нужны поля course_id и text_content'}), 400

    if not Course.query.get(data['course_id']):
        return jsonify({'error': 'Курс не найден'}), 404

    lesson = Lesson(
        course_id=data['course_id'],
        type='text',
        title=data.get('title', 'Лекция'),
        order=data.get('order', 0),
        text_content=data['text_content'],
    )
    db.session.add(lesson)
    db.session.commit()
    return jsonify(lesson.to_dict()), 201


@lessons_bp.route('/api/lessons/<int:lesson_id>/questions', methods=['POST'])
@jwt_required()
def add_question(lesson_id):
    """
    Добавить контрольный вопрос к уроку.
    timestamp_seconds — на какой секунде видео показать вопрос (необязательно).
    options — список вариантов ответа, correct_answer — верный вариант (строка).
    """
    if not _check_is_master():
        return jsonify({'error': 'Добавлять вопросы может только мастер'}), 403

    lesson = Lesson.query.get_or_404(lesson_id)
    data = request.get_json()

    required = ['question_text', 'options', 'correct_answer']
    if not all(f in data for f in required):
        return jsonify({'error': 'Нужны поля question_text, options, correct_answer'}), 400

    question = Question(
        lesson_id=lesson.id,
        timestamp_seconds=data.get('timestamp_seconds'),
        question_text=data['question_text'],
        options_json=json.dumps(data['options'], ensure_ascii=False),
        correct_answer=data['correct_answer'],
    )
    db.session.add(question)
    db.session.commit()
    return jsonify(question.to_dict(hide_answer=True)), 201