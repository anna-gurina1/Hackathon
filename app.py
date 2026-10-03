from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config, init_cloudinary
from models import db

from routes.auth import auth_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.enrollment import enrollment_bp


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