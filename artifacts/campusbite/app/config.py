import os
from datetime import timedelta


def _is_production() -> bool:
    return os.environ.get("FLASK_ENV", "").lower() == "production"


class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or os.environ.get("SESSION_SECRET")
        or (None if _is_production() else "campusbite-local-development-only")
    )
    # Keep this artifact separate from a workspace-level DATABASE_URL which may
    # belong to a different app or database.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "CAMPUSBITE_DATABASE_URL", "sqlite:///campusbite.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _is_production()
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_TIME_LIMIT = 3600
    RATELIMIT_STORAGE_URI = "memory://"
    LOW_STOCK_THRESHOLD = 5
    CAMPUS_TIMEZONE = "Asia/Karachi"
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
