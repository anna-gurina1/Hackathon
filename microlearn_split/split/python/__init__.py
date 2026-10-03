import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.home"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.main import bp as main_bp
    from app.routes.auth import bp as auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"now_year": datetime.now().year}

    with app.app_context():
        from app import models  # noqa: F401  (registers models)

        db.create_all()

    return app
