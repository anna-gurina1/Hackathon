import os

from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFError, CSRFProtect

from core.config import BASE_DIR, Config
from database import db, migrate

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
    # absolute path, so migrations are found from any folder the server is started in
    migrate.init_app(app, db, directory=os.path.join(BASE_DIR, "migrations"))
    csrf.init_app(app)
    login_manager.init_app(app)

    from backend.routes.site_auth import bp as auth_bp
    from backend.routes.main import bp as main_bp
    from backend.routes.courses import bp as courses_bp
    from backend.routes.builder import bp as builder_bp
    from backend.routes.quiz import bp as quiz_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(builder_bp)
    app.register_blueprint(quiz_bp)

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

        if app.config.get("TESTING"):
            # Tests use a throw-away in-memory database: no migrations needed.
            db.create_all()
        else:
            # The real database is created and updated with migrations (migrations/versions/).
            # They run automatically on every start, so after `git pull` nobody has to
            # remember `flask db upgrade` (it still works and does the same thing).
            from flask_migrate import upgrade
            from sqlalchemy import inspect

            try:
                upgrade()
            except Exception:  # never stop the site from starting because of this
                app.logger.exception("Automatic database upgrade failed. Run:  flask db upgrade")

            tables = inspect(db.engine)

            # A fresh database gets the demo company and demo courses, so there is
            # something to try right after signing up. Skipped while there are no tables.
            if tables.has_table("user"):
                from sqlalchemy.exc import OperationalError

                from database.seed import ensure_demo_data

                try:
                    ensure_demo_data()
                except OperationalError:
                    # models.py has a new column that this app.db does not have yet.
                    # Skip the demo data so `flask db upgrade` itself can start.
                    db.session.rollback()
                    app.logger.warning(
                        "The database is older than models.py. Run:  flask db upgrade"
                    )

    return app
