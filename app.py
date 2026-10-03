from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config, init_cloudinary
from models import db

from backend.routes.auth import auth_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)
    JWTManager(app)
    db.init_app(app)
    init_cloudinary()

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
