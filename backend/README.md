# backend/ — логика

Маршруты (что происходит при открытии страницы или отправке формы).

- `routes/main.py` — главная, Tips, аккаунт
- `routes/auth.py` — регистрация, вход по ссылке на email, выход
- `email.py` — отправка писем (без MAIL_SERVER письма печатаются в терминал)

Новые страницы — новый файл в `routes/` (например `courses.py`), потом лид добавляет его в `core/__init__.py`.
Таблицы берём из `database.models`, шаблон — `render_template("имя.html", ...)` из `frontend/templates`.
