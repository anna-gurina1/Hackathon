"""Маршруты для аудио:
    POST /audio/upload   — загрузить mp3/wav в базу (поле формы "audio", необязательно "lesson_id")
    GET  /audio/<id>     — отдать файл (для <audio src="..."> и скачивания)
"""
from io import BytesIO

from flask import Blueprint, abort, jsonify, request, send_file, url_for
from flask_login import current_user, login_required

from backend.audio import save_audio
from database import db
from database.models import AudioFile, Lesson
from database.queries import course_visible_to

bp = Blueprint("audio", __name__)


@bp.route("/audio/upload", methods=["POST"])
@login_required
def upload():
    lesson_id = request.form.get("lesson_id", type=int)

    if lesson_id is not None:
        lesson = db.session.get(Lesson, lesson_id)
        if lesson is None:
            abort(404)
        # добавлять аудио к уроку может только компания-владелец курса
        if lesson.course.company_id != current_user.id:
            abort(403)

    try:
        audio = save_audio(request.files.get("audio"), current_user.id, lesson_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({
        "id": audio.id,
        "filename": audio.filename,
        "size": audio.size,
        "url": url_for("audio.stream", audio_id=audio.id),
    }), 201


@bp.route("/audio/<int:audio_id>")
def stream(audio_id):
    audio = db.session.get(AudioFile, audio_id)
    if audio is None:
        abort(404)

    if audio.lesson is not None:
        # аудио урока видно тем же, кому виден курс
        if not course_visible_to(audio.lesson.course, current_user):
            abort(403)
    elif not current_user.is_authenticated or audio.uploader_id != current_user.id:
        # аудио без урока видит только тот, кто его загрузил
        abort(403)

    # conditional=True включает поддержку Range, поэтому перемотка в <audio> работает
    return send_file(
        BytesIO(audio.data),
        mimetype=audio.mime_type,
        download_name=audio.filename,
        conditional=True,
    )