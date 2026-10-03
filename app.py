from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config, init_cloudinary
from models import db

from backend.routes.auth import auth_bp
from backend.routes.courses import courses_bp
from backend.routes.lessons import lessons_bp
from backend.routes.enrollment import enrollment_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app) 
    JWTManager(app)
    db.init_app(app)
    init_cloudinary()

    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(lessons_bp)
    app.register_blueprint(enrollment_bp)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)