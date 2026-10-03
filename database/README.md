# database/ — хранение данных

- `__init__.py` — общий объект `db`
- `models.py` — все таблицы (см. список ниже)
- `seed.py` — демо-данные: `python -m database.seed` из корня проекта (пересоздаёт базу)

База — SQLite, файл `app.db` в корне (не в гите). После изменения таблиц удалите `app.db` или
перезапустите `python -m database.seed` — она создастся заново.

## Таблицы

- **User** — аккаунт: `type` (person/company), `email`, `login_nonce`; связи `person`, `company`.
- **PersonProfile** — `first_name`, `last_name` человека.
- **CompanyProfile** — `name`, `description` компании.
- **Course** — курс: `title`, `topic`, `profession`, `outcome`, `level`, `knowledge_type`, `duration`, `is_private`, `invite_token`, `status`, `yes_answers`; принадлежит компании (`company_id`).
- **Lesson** — урок курса: `order`, `title`, `question_id` (ссылка на `core.questions`), `video_filename`, `text`.
- **Quiz** — тест одного урока: `pass_score` (процент для прохождения).
- **QuizQuestion** — вопрос теста: `text`, `category` (категория из `core.questions.CATEGORIES`).
- **QuizAnswer** — вариант ответа: `text`, `is_correct`.
- **Enrollment** — запись человека на курс: `status`, `current_lesson`, `started_at`, `completed_at`; уникальна пара (user, course).
- **QuizAttempt** — попытка сдачи теста: `score`, `passed`.
- **Offer** — предложение о работе от компании человеку по курсу: `text`.

Удаление курса каскадно удаляет его уроки, тесты, вопросы, ответы, записи и предложения.
Видеофайл с диска не удаляется автоматически — для этого backend вызывает `Lesson.delete_video_file(upload_folder)`.