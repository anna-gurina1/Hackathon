"""Видео уроков хранятся в Cloudinary. В базе (Lesson.video_filename) лежит только public_id.

Главные функции для остальной команды (вход/выход те же, что были раньше):
    save_video(file_storage) -> str    загружает видео, возвращает public_id для Lesson.video_filename
    delete_video(public_id)  -> bool   удаляет видео из Cloudinary
    video_url(public_id)     -> str    https-ссылка для <video src="...">; в шаблоне проще lesson.video_url

Ключи берутся из файла .env (он НЕ должен попадать в git):
    CLOUDINARY_CLOUD_NAME=...
    CLOUDINARY_API_KEY=...
    CLOUDINARY_API_SECRET=...
(или одной переменной CLOUDINARY_URL=cloudinary://key:secret@cloud_name)
"""
import logging
import os

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from cloudinary.exceptions import Error as CloudinaryError
from dotenv import load_dotenv

ALLOWED_EXTENSIONS = {"mp4", "webm", "mov"}
CLOUDINARY_FOLDER = "hackathon-lessons"  # папка в Cloudinary, чтобы видео не лежали кучей в корне
CHUNK_SIZE = 20 * 1024 * 1024            # большие видео уходят кусками по 20 МБ

log = logging.getLogger(__name__)
_configured = False


def _configure():
    """Один раз подключает Cloudinary. Бросает RuntimeError, если ключей нет."""
    global _configured
    if _configured:
        return

    load_dotenv()
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    if cloud_name:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )

    # если задан CLOUDINARY_URL, библиотека сама заполнит config() при импорте
    if not cloudinary.config().cloud_name:
        raise RuntimeError(
            "Cloudinary is not configured: set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET in the .env file."
        )
    _configured = True


def _extension(filename):
    """Расширение в нижнем регистре без точки или пустая строка."""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def save_video(file_storage):
    """Загружает видео в Cloudinary и возвращает его public_id (для Lesson.video_filename).

    Бросает ValueError с понятным текстом, если файл не выбран, у него
    неподдерживаемый формат или загрузка не удалась.
    """
    if file_storage is None or not file_storage.filename:
        raise ValueError("No video file selected.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported video format. Allowed formats: {allowed}.")

    _configure()

    file_storage.stream.seek(0)
    try:
        result = cloudinary.uploader.upload_large(
            file_storage.stream,
            resource_type="video",  # обязательно, иначе Cloudinary сохранит файл как raw
            asset_folder=CLOUDINARY_FOLDER,  # у тебя Dynamic folders, поэтому asset_folder, а не folder
            chunk_size=CHUNK_SIZE,
        )
    except (CloudinaryError, OSError):
        log.exception("Cloudinary video upload failed")
        raise ValueError("Could not upload the video. Please try again.")

    return result["public_id"]


def delete_video(public_id):
    """Удаляет видео из Cloudinary. Возвращает True, если удалено.

    Безопасно вызывать с None, пустым значением или несуществующим видео.
    """
    if not public_id:
        return False

    _configure()
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="video", invalidate=True)
    except (CloudinaryError, OSError):
        log.exception("Cloudinary video delete failed")
        return False
    return result.get("result") == "ok"


def video_url(public_id):
    """https-ссылка на видео (mp4) или None, если видео нет."""
    if not public_id:
        return None

    _configure()
    url, _options = cloudinary.utils.cloudinary_url(
        public_id, resource_type="video", secure=True, format="mp4"
    )
    return url