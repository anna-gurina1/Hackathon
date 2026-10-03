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
import shutil
import subprocess
import tempfile

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from cloudinary.exceptions import Error as CloudinaryError
from dotenv import load_dotenv

ALLOWED_EXTENSIONS = {"mp4", "webm", "mov"}
CLOUDINARY_FOLDER = "hackathon-lessons"  # папка в Cloudinary, чтобы видео не лежали кучей в корне
CHUNK_SIZE = 20 * 1024 * 1024            # большие видео уходят кусками по 20 МБ
MAX_VIDEO_BYTES = 100 * 1024 * 1024      # лимит бесплатного тарифа Cloudinary на одно видео

# Если видео больше лимита, оно автоматически сжимается через ffmpeg.
# Попытки по порядку: (максимальная высота кадра, CRF). Больше CRF = меньше файл, хуже качество.
COMPRESS_ATTEMPTS = [(720, 28), (480, 32)]
COMPRESS_TIMEOUT = 15 * 60               # секунд на одно сжатие

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


def _find_ffmpeg():
    """Путь к ffmpeg: сначала тот, что ставится вместе с imageio-ffmpeg, потом системный."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _compress(stream, ext, workdir):
    """Сжимает видео в mp4 до размера <= MAX_VIDEO_BYTES. Возвращает путь к готовому файлу.

    Бросает ValueError, если ffmpeg не найден или видео не удалось уменьшить.
    """
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        log.error("ffmpeg not found: run `pip install imageio-ffmpeg`")
        raise ValueError(
            f"The video is larger than {MAX_VIDEO_BYTES // (1024 * 1024)} MB "
            "and the server cannot compress it."
        )

    src = os.path.join(workdir, f"source.{ext}")
    dst = os.path.join(workdir, "compressed.mp4")
    with open(src, "wb") as f:
        shutil.copyfileobj(stream, f)

    for height, crf in COMPRESS_ATTEMPTS:
        command = [
            ffmpeg, "-y", "-i", src,
            "-vf", f"scale=-2:'min({height},ih)'",   # не больше height пикселей по высоте, не растягиваем маленькое
            "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",               # видео начинает играть до полной загрузки
            dst,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=COMPRESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            log.error("ffmpeg timed out")
            raise ValueError("Compressing the video took too long. Try a shorter video.")
        except subprocess.CalledProcessError as error:
            log.error("ffmpeg failed: %s", error.stderr.decode(errors="replace")[-500:])
            raise ValueError("Could not compress the video. Is it a valid video file?")
        except OSError:
            log.exception("could not start ffmpeg")
            raise ValueError("Could not compress the video.")

        if os.path.getsize(dst) <= MAX_VIDEO_BYTES:
            return dst

    raise ValueError(
        f"Even after compression the video is larger than {MAX_VIDEO_BYTES // (1024 * 1024)} MB. "
        "Try a shorter video."
    )


def save_video(file_storage):
    """Загружает видео в Cloudinary и возвращает его public_id (для Lesson.video_filename).

    Видео больше 100 МБ автоматически сжимается через ffmpeg.
    Бросает ValueError с понятным текстом, если файл не выбран, у него
    неподдерживаемый формат, его не удалось сжать или загрузка не удалась.
    """
    if file_storage is None or not file_storage.filename:
        raise ValueError("No video file selected.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported video format. Allowed formats: {allowed}.")

    _configure()

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size == 0:
        raise ValueError("The video file is empty.")

    # временная папка удалится сама, даже если что-то пошло не так
    with tempfile.TemporaryDirectory() as workdir:
        if size > MAX_VIDEO_BYTES:
            path = _compress(stream, ext, workdir)   # слишком большое видео сжимаем
            source = open(path, "rb")
        else:
            source = stream

        try:
            result = cloudinary.uploader.upload_large(
                source,
                resource_type="video",  # обязательно, иначе Cloudinary сохранит файл как raw
                asset_folder=CLOUDINARY_FOLDER,  # у тебя Dynamic folders, поэтому asset_folder, а не folder
                chunk_size=CHUNK_SIZE,
            )
        except (CloudinaryError, OSError):
            log.exception("Cloudinary video upload failed")
            raise ValueError("Could not upload the video. Please try again.")
        finally:
            if source is not stream:
                source.close()

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


# ---------- Картинки: фото профиля и логотип компании ----------

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CLOUDINARY_AVATAR_FOLDER = "hackathon-avatars"


def save_image(file_storage):
    """Загружает фото профиля / логотип в Cloudinary и возвращает public_id (для User.avatar).

    Картинка сразу обрезается в квадрат 400x400 (по лицу или главному объекту).
    Бросает ValueError с понятным текстом, RuntimeError если Cloudinary не настроен.
    """
    if file_storage is None or not file_storage.filename:
        raise ValueError("No image selected.")

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image format. Allowed formats: png, jpg, webp, gif.")

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size == 0:
        raise ValueError("The image file is empty.")
    if size > MAX_IMAGE_BYTES:
        raise ValueError("The image is too big (max 5 MB).")

    _configure()
    try:
        result = cloudinary.uploader.upload(
            stream,
            resource_type="image",
            asset_folder=CLOUDINARY_AVATAR_FOLDER,
            transformation=[{"width": 400, "height": 400, "crop": "fill", "gravity": "auto"}],
        )
    except (CloudinaryError, OSError):
        log.exception("Cloudinary image upload failed")
        raise ValueError("Could not upload the image. Please try again.")
    return result["public_id"]


def delete_image(public_id):
    """Удаляет картинку из Cloudinary. Безопасно вызывать с None."""
    if not public_id or public_id.startswith("static:"):  # демо-логотип из frontend/static — не трогаем
        return False
    _configure()
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)
    except (CloudinaryError, OSError):
        log.exception("Cloudinary image delete failed")
        return False
    return result.get("result") == "ok"


def image_url(public_id, size=200):
    """https-ссылка на квадратную картинку size x size или None."""
    if not public_id:
        return None
    _configure()
    url, _options = cloudinary.utils.cloudinary_url(
        public_id, resource_type="image", secure=True,
        width=size, height=size, crop="fill", gravity="auto", fetch_format="auto",
    )
    return url
