# backend/ — логика

Маршруты (что происходит при открытии страницы или отправке формы).

Сайт (запуск через `python run.py`, подключены в `core/__init__.py`):
- `routes/main.py` — главная, Explore (поиск), аккаунт
- `routes/site_auth.py` — регистрация, вход по ссылке на email, выход
- `email.py` — отправка писем (без MAIL_SERVER письма печатаются в терминал)

API-версия (JWT, запуск через корневой `app.py`, пока отдельно от сайта):
- `routes/auth.py`, `routes/courses.py`, `routes/lessons.py`, `routes/enrollment.py`

Новые страницы — новый файл в `routes/`, потом лид добавляет его в `core/__init__.py`.
Таблицы берём из `database.models`, шаблон — `render_template("имя.html", ...)` из `frontend/templates`.
