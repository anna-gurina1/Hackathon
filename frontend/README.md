# frontend/ — интерфейс

- `templates/` — страницы Jinja (`base.html` — шапка, окно входа, футер)
- `static/css/style.css` — единый файл стилей, цвета и шрифты в переменных `:root` (согласуется с design/)
- `static/js/main.js` — меню аватара, окно входа, вкладки, переключатель person/company

Ссылки на файлы: `url_for('static', filename='css/style.css')`.
В каждой форме с method="post" нужна строка:
`<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
Какие переменные приходят в шаблон — договариваемся с backend и записываем в ARCHITECTURE.md.
