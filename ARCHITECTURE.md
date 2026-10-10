Таблицы и поля:
Course: компания, название, описание, тема, профессия, уровень, длительность, public/private, токен для приватной ссылки;
Lesson: курс, порядок, вопрос мастеру, видео, текст;
Quiz, Question, Answer: тест урока, вопросы, варианты ответов, правильный ответ;
Enrollment: человек, курс, статус, текущий урок;
QuizAttempt: человек, тест, результат;
Offer: компания, человек, курс, текст.
Адреса страниц: /course/new, /course/<id>/builder, /course/<id>, /course/<id>/lesson/<n>/quiz, /course/private/<token>, /account.
Что передаётся в каждый шаблон: например, course, lessons, progress, questions.

## Тарифы (backend/plans.py)
Оплаты нет, это демо: кнопка на /pricing просто включает тариф. Лимиты проверяет бэкенд, фронт только прячет кнопки.

| plan | курсов | видео в одном курсе | приватные курсы |
|---|---|---|---|
| "free" | 1 | 3 | нет |
| "per_course" | 1 + course_credits (куплено) | 10 | да |
| "monthly" | без лимита | без лимита | да |

Курсы считаются все, включая черновики. Удалённый курс освобождает место. Длина видео нигде не ограничена.
Поля CompanyProfile: plan (строка, по умолчанию "free"), course_credits (число, по умолчанию 0). CompanyProfile.is_pro — свойство: True для "per_course" и "monthly".

Константы: PLAN_LABELS = {"free": "Free", "per_course": "Per course", "monthly": "Monthly"}, VIDEO_LIMITS = {"free": 3, "per_course": 10, "monthly": None} (None = без лимита).

| функция | вход | выход |
|---|---|---|
| plan_of(company_user) | пользователь-компания | ключ тарифа ("free" / "per_course" / "monthly"); неизвестное значение = "free" |
| course_limit(company_user) | пользователь-компания | int или None (None = без лимита) |
| courses_used(company_user) | пользователь-компания | int, все курсы компании (черновики тоже) |
| can_create_course(company_user) | пользователь-компания | bool: лимит None или courses_used < лимита |
| video_limit(company_user) | пользователь-компания | int или None |
| videos_used(course) | курс | int, уроки курса, у которых есть video_filename |
| can_add_video(course) | курс | bool: лимит None или videos_used < лимита |

Где проверяется:
- courses.new (GET и POST): нет места под курс -> flash "You have used all courses on your plan. Choose a plan to add more." и redirect на main.pricing.
- courses.new и courses.edit: private на Free -> курс остаётся public + flash "Private courses are a Pro feature. The course stays public."
- builder.add_lesson: новое видео при can_add_video == False -> урок не создаётся, видео не загружается, flash "Your plan allows N videos per course. Upgrade to add more.", redirect на builder.script.
- builder.edit_lesson: то же для урока без видео. Замена видео в уроке, где оно уже есть, не считается новым видео и разрешена.

Демо-оплата: POST /pricing/choose (main.choose_plan), только компания (person -> 403), поле plan = "free" | "per_course" | "monthly" (другое -> 400).
"per_course": plan = "per_course", course_credits += 1. "monthly": plan = "monthly". "free": plan = "free" (курсы не удаляются). Потом flash "Plan updated: <label>." и redirect на main.account.

Переменные шаблонов:
- pricing.html: current_plan (str или None для гостя и person).
- account_company.html (кроме прежних): plan_label, course_limit (int или None), courses_used, can_create_course.
- builder.html (кроме прежних): video_limit (int или None), videos_used, can_add_video.
## Языки (EN / RU)
- Весь текст интерфейса пишется в коде на английском и оборачивается в `_("...")` (Python и шаблоны) или `t("...")` (JavaScript). Английский текст сам служит ключом.
- Переводы лежат в `translations/ru/`: `interface.json` (шаблоны), `messages.json` (flash-сообщения, письма, ошибки), `questions.json` (вопросы мастера, подсказки, категории, уровни, шаблоны квиза), `scripts.json` (тексты для JS). Если перевода нет, показывается английский.
- Числа с окончаниями: `_n("{count} course", "{count} courses", count)`; в JSON для русского значение — список из 3 форм: `["{count} курс", "{count} курса", "{count} курсов"]`.
- Текст с HTML-разметкой: `_html(...)` (подставленные значения экранируются). Даты: `format_date(date)`.
- Выбор языка (`backend/i18n.py`, `current_language()`): cookie `lang` → `User.language` → заголовок Accept-Language браузера → английский.
- Переключатель EN/RU в шапке рядом с Home ведёт на `/language/<code>?next=...`: ставит cookie на год и сохраняет язык в профиль, если пользователь вошёл.
- Письма другим людям отправляются на языке получателя (`with use_language(user.language): ...`).
- Пользовательский контент (курсы, уроки, названия компаний) не переводится.
- Проверка переводов: `python translations/check.py` — покажет недостающие переводы и ошибки в `{подстановках}`.
- Новый язык: создать `translations/<код>/` с теми же файлами и добавить код в `LANGUAGES` в `backend/i18n.py`.
- Переключатель в шапке — одна ссылка: нажатие в любом месте переключает на следующий язык (EN → RU → EN). Подсказка написана на том языке, на который переключаем (`SWITCH_LABELS` в `backend/i18n.py`). Анимация — в `main.js` и `style.css` (`.lang-switch`).

## Кнопка «Перевести» (backend/translator.py)
- Если текст пользователя (курс, урок, тест, описание компании, предложение работы) написан не на языке сайта, рядом появляется кнопка «Перевести». Язык текста определяется без ИИ: каких букв больше — латиницы или кириллицы.
- В шаблоне: `{% set t = offer_translation(course, "description") %}` → `{{ course.description }}{{ t.button }}` и ниже `{{ t.box }}`. Можно передать список объектов и подписи: `offer_translation(lessons, "title", labels=[...])`.
- Страница отправляет на `POST /api/translate` не сам текст, а подписанную ссылку на поле (какая таблица, id, поле), поэтому переводится только то, что сайт действительно показывает.
- Переводит ИИ из `.env` (`backend/ai_tips.py`) в быстром режиме — без долгого «размышления» модели (`quick=True`). Для перевода можно указать отдельную модель: `GEMINI_TRANSLATION_MODEL`. После первого нажатия `main.js` в фоне одним запросом переводит все остальные блоки страницы, поэтому следующие кнопки открываются сразу. Переводы ничего не переводят заранее: перевод сохраняется в таблицу `translation` в момент первого нажатия, следующие читатели получают его мгновенно. Изменённый автором текст переводится заново.

## Язык курса и отметки мастера
- `Course.language` ("en"/"ru") определяется при сохранении курса (`course.update_language()`). В каталоге — метка EN/RU и переключатель «Только курсы на русском/английском» (`/api/search?...&lang=ru`).
- Кнопки «Взять» больше нет. Мастер может отметить ✓ вопросы-подсказки, на которые уже ответил (таблица `answered_question`, `POST /course/<id>/questions/<question_id>/answered`). Отметки видит только он, к урокам они не привязаны. У старых уроков `Lesson.question_id` сохранён — он только подбирает идеи для теста; новым урокам показываются общие идеи.
