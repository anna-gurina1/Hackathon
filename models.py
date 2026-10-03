from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """Пользователь системы: мастер, сотрудник или компания."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'master' | 'student' | 'company'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'email': self.email, 'role': self.role}


class Course(db.Model):
    """Курс, который создаёт мастер."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    master_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Если курс приватный — доступен только сотрудникам конкретной компании
    is_private = db.Column(db.Boolean, default=False)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lessons = db.relationship('Lesson', backref='course', cascade='all, delete-orphan')

    def to_dict(self, include_lessons=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'master_id': self.master_id,
            'is_private': self.is_private,
            'company_id': self.company_id,
        }
        if include_lessons:
            data['lessons'] = [l.to_dict() for l in sorted(self.lessons, key=lambda x: x.order)]
        return data


class Lesson(db.Model):
    """Урок внутри курса: видео или текст (лекция)."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'video' | 'text'
    order = db.Column(db.Integer, default=0)

    title = db.Column(db.String(200))

    text_content = db.Column(db.Text, nullable=True)

    video_url = db.Column(db.String(500), nullable=True)
    video_public_id = db.Column(db.String(300), nullable=True)  
    questions = db.relationship('Question', backref='lesson', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'type': self.type,
            'order': self.order,
            'title': self.title,
            'text_content': self.text_content,
            'video_url': self.video_url,
            'questions': [q.to_dict() for q in self.questions],
        }


class Question(db.Model):
    """Контрольный вопрос, привязанный к уроку (и опционально к моменту видео)."""
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)

    timestamp_seconds = db.Column(db.Integer, nullable=True)

    question_text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False)  # храним список вариантов как JSON-строку
    correct_answer = db.Column(db.String(300), nullable=False)

    def to_dict(self, hide_answer=True):
        import json
        data = {
            'id': self.id,
            'lesson_id': self.lesson_id,
            'timestamp_seconds': self.timestamp_seconds,
            'question_text': self.question_text,
            'options': json.loads(self.options_json),
        }
        if not hide_answer:
            data['correct_answer'] = self.correct_answer
        return data


class Enrollment(db.Model):
    """Запись о прохождении курса конкретным сотрудником — итоговый статус."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    status = db.Column(db.String(20), default='in_progress')  # 'in_progress' | 'completed'
    score = db.Column(db.Integer, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'status': self.status,
            'score': self.score,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class CourseLog(db.Model):
    """Подробный лог действий: кто, что и когда сделал внутри курса."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=True)

    # Примеры action: 'started_lesson', 'answered_question', 'completed_course'
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)  # произвольный JSON с подробностями
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_id': self.course_id,
            'lesson_id': self.lesson_id,
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
        }