from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event

db = SQLAlchemy()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300 per day", "90 per hour"],
    storage_uri="memory://",
)


def enable_sqlite_foreign_keys(app) -> None:
    with app.app_context():
        engine = db.engine
        if engine.dialect.name != "sqlite":
            return

        @event.listens_for(engine, "connect")
        def _set_sqlite_foreign_keys(connection, _connection_record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
