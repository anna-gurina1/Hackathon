import os

from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFError, CSRFProtect

from core.config import BASE_DIR, Config
from database import db

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "main.home"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    from database.models import User

    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    # Pages and styles live in the frontend/ folder
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
        static_folder=os.path.join(BASE_DIR, "frontend", "static"),
    )
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from backend.routes.auth import bp as auth_bp
    from backend.routes.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_globals():
        from datetime import datetime

        return {"now_year": datetime.now().year}

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return render_template("errors/403.html"), 403

    with app.app_context():
        import database.models  # noqa: F401  (registers the tables)

        db.create_all()

    return app
