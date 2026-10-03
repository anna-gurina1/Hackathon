"""Сохранение и удаление видеофайлов в папке UPLOAD_FOLDER (uploads/)."""
import os
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"mp4", "webm", "mov"}


def _extension(filename):
    """Расширение в нижнем регистре без точки или пустая строка."""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def save_video(file_storage):
    """Сохраняет загруженное видео и возвращает имя файла (для Lesson.video_filename).

    Бросает ValueError с понятным текстом, если файл не выбран
    или у него неподдерживаемый формат.
    """
    if file_storage is None or not file_storage.filename:
        raise ValueError("No video file selected.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported video format. Allowed formats: {allowed}.")

    # secure_filename убирает небезопасные символы; для имён вроде "видео.mp4"
    # он может вернуть пустую строку или только расширение — тогда берём запасное имя.
    stem = file_storage.filename.rsplit(".", 1)[0]
    safe_stem = secure_filename(stem) or "video"
    filename = f"{uuid4().hex}_{safe_stem}.{ext}"

    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, filename))
    return filename


def delete_video(filename):
    """Удаляет видео с диска. Возвращает True, если файл был удалён.

    Безопасно вызывать с None, пустым именем или несуществующим файлом.
    """
    if not filename:
        return False

    # Защита от выхода за пределы папки (../ и т.п.): работаем только с именем файла.
    if os.path.basename(filename) != filename:
        return False

    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    try:
        os.remove(path)
    except FileNotFoundError:
        return False
    return True
