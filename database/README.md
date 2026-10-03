# database/ — хранение данных

- `__init__.py` — общий объект `db`
- `models.py` — таблицы: `User` (person | company), `PersonProfile`, `CompanyProfile`

Сюда добавляются Course, Lesson, Quiz, Question, Answer, Enrollment, QuizAttempt, Offer.
База — SQLite, файл `app.db` в корне (не в гите). После изменения таблиц удалите `app.db`, она создастся заново.
