# Изменения контракта: студия курса, без типа знаний

Это нужно вставить в общий контракт (prompt_backend.md) — разделы указаны. Всё остальное в контракте не меняется.

## 1. Продукт (заменить абзац)
Компания нажимает «Create course» и попадает на минималистичную страницу: сверху общие советы, ниже большой «+».
По «+» открываются поля курса: title, description, topic, profession, outcome, level, visibility. Типа знаний и длительности больше нет.
После создания открывается студия курса (`builder.script`): список уроков, большой «+» для нового урока и сбоку
рекомендуемые вопросы из `core/questions.py` для уровня курса. Урок = title + видео и/или текст; вопрос сбоку можно подставить
в урок кнопкой «Use» (тогда сохраняется `question_id`). Время — только совет («1–3 min per lesson»), нигде не проверяется.
Курс public или private. Private доступен любой компании бесплатно: он не попадает в поиск и открывается только по ссылке-приглашению.

## 2. Модели (database/models.py)
- `Course`: `knowledge_type` и `duration` сделать `nullable=True` (форма их больше не присылает). `yes_answers` больше не используется.

## 3. Подбор вопросов (core/course_builder.py)
`select_questions(...)` больше не нужен для студии. Нужна функция:
```
recommended_questions(level) -> list[dict]
# [{"category": "goal", "category_label": "Learning goal", "questions": [<dict из QUESTIONS>, ...]}, ...]
# берёт QUESTIONS, где level in q["levels"] и q["answer_type"] == "media";
# категорию "video_quality" пропускает (это советы по съёмке); порядок — как в CATEGORIES.
# level=None -> все уровни (для страницы нового курса, там список фильтрует JS).
```

## 4. Адреса — заменить таблицы
**courses**
| endpoint | URL | доступ | шаблон |
|---|---|---|---|
| courses.new | GET/POST /course/new | компания | course_form.html → после POST redirect builder.script |
| courses.edit | GET/POST /course/<int:course_id>/edit | владелец | course_form.html → после POST redirect builder.script |
(остальные endpoint'ы courses без изменений)

Правило для new/edit: `visibility` берётся из формы как есть: `"private"` → приватный курс (invite-токен создаётся как раньше), любое другое значение → public.

**builder** (вместо `builder.answer`)
| endpoint | URL | доступ | шаблон |
|---|---|---|---|
| builder.script | GET /course/<int:course_id>/builder | владелец | builder.html |
| builder.add_lesson | POST /course/<int:course_id>/lessons | владелец | → redirect builder.script#lesson-<id> |
| builder.edit_lesson | POST /course/<int:course_id>/lessons/<int:lesson_id> | владелец | → redirect builder.script#lesson-<id> |
| builder.delete_lesson | POST /course/<int:course_id>/lessons/<int:lesson_id>/delete | владелец | → redirect builder.script (order уроков пересчитать 1..n) |
| builder.quiz_edit | GET/POST /course/<int:course_id>/lesson/<int:lesson_id>/quiz/edit | владелец | quiz_edit.html (без изменений) |

Поля формы урока: `title` (обязательно), `text`, `video` (файл, необязательно), `question_id` (пусто или id из QUESTIONS).
В edit_lesson новое видео заменяет старое (старый файл удалить через `delete_video`), пустое поле video — оставить старое.

**main**
| endpoint | URL | доступ | шаблон |
|---|---|---|---|
| main.explore | GET /explore | все | explore.html (страница поиска, бывшая tips) |

## 5. Переменные шаблонов — заменить
- **course_form.html**: `course` (Course | None), `LEVELS`, `recommended` (= recommended_questions(None)).
  Поля: `title, description, topic, profession, outcome, level, visibility`.
- **builder.html**: `course`, `lessons`, `recommended` (= recommended_questions(course.level)),
  `used_question_ids` (set id вопросов, по которым уже есть уроки).
- Убрать из контракта: `TYPES`, `DURATIONS` в шаблонах, `script/answered/total` в builder.html.
