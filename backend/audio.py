"""Хранение mp3/wav прямо в SQLite (колонка BLOB в таблице AudioFile).

Главные функции для остальной команды:
    save_audio(file_storage, uploader_id, lesson_id=None) -> AudioFile
    delete_audio(audio) -> None

Файл читается в память целиком, поэтому есть лимит MAX_AUDIO_BYTES.
Для длинных записей (сотни МБ) лучше хранить файл на диске, а в базе только имя.
"""
import os

ALLOWED_AUDIO = {"mp3": "audio/mpeg", "wav": "audio/wav"}
MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20 MB


def _extension(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def _looks_like(ext, data):
    """Проверяем первые байты, а не только расширение (чтобы .mp3 не оказался чем-то другим)."""
    if ext == "wav":
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if ext == "mp3":
        # ID3-тег в начале, либо сразу MPEG-кадр (11 бит синхронизации)
        return data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    return False


def check_audio(filename, data):
    """Возвращает mime-type или бросает ValueError с понятным текстом."""
    ext = _extension(filename)
    if ext not in ALLOWED_AUDIO:
        allowed = ", ".join(sorted(ALLOWED_AUDIO))
        raise ValueError(f"Unsupported audio format. Allowed formats: {allowed}.")
    if not data:
        raise ValueError("The audio file is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError(f"Audio file is too large (max {MAX_AUDIO_BYTES // (1024 * 1024)} MB).")
    if not _looks_like(ext, data):
        raise ValueError(f"The file does not look like a real .{ext} file.")
    return ALLOWED_AUDIO[ext]


def save_audio(file_storage, uploader_id, lesson_id=None):
    """Кладёт загруженный mp3/wav в базу и возвращает объект AudioFile.

    file_storage — это request.files["audio"].
    Бросает ValueError, если файл не выбран, не mp3/wav или слишком большой.
    """
    from database import db
    from database.models import AudioFile

    if file_storage is None or not file_storage.filename:
        raise ValueError("No audio file selected.")

    # читаем максимум на 1 байт больше лимита, чтобы не грузить в память гигабайты
    data = file_storage.read(MAX_AUDIO_BYTES + 1)
    mime = check_audio(file_storage.filename, data)

    audio = AudioFile(
        uploader_id=uploader_id,
        lesson_id=lesson_id,
        filename=os.path.basename(file_storage.filename)[:255],
        mime_type=mime,
        size=len(data),
        data=data,
    )
    db.session.add(audio)
    db.session.commit()
    return audio


def delete_audio(audio):
    from database import db

    db.session.delete(audio)
    db.session.commit()