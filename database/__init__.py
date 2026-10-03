from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# One shared database object for the whole project
db = SQLAlchemy()

# Schema changes: `flask db upgrade` (see migrations/ and README.md)
migrate = Migrate()
