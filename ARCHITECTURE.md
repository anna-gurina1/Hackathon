Таблицы и поля:
Course: компания, название, описание, тема, профессия, уровень, длительность, public/private, токен для приватной ссылки;
Lesson: курс, порядок, вопрос мастеру, видео, текст;
Quiz, Question, Answer: тест урока, вопросы, варианты ответов, правильный ответ;
Enrollment: человек, курс, статус, текущий урок;
QuizAttempt: человек, тест, результат;
Offer: компания, человек, курс, текст.
Адреса страниц: /course/new, /course/<id>/builder, /course/<id>, /course/<id>/lesson/<n>/quiz, /course/private/<token>, /account.
Что передаётся в каждый шаблон: например, course, lessons, progress, questions.