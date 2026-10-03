from werkzeug.datastructures import FileStorage
from backend.uploads import save_video, video_url, delete_video

with open("test.mp4", "rb") as f:
    public_id = save_video(FileStorage(f, filename="test.mp4"))

print("public_id:", public_id)
print("ссылка:", video_url(public_id))

input("Открой ссылку в браузере, потом нажми Enter, чтобы удалить тестовое видео...")
print("удалено:", delete_video(public_id))