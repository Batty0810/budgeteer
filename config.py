import os
from datetime import timedelta

from sqlalchemy.pool import StaticPool

basedir = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url):
    """Fly/Heroku-style Postgres URLs use the 'postgres://' scheme, which
    SQLAlchemy 2.x rejects, and don't specify a driver. Rewrite to the
    psycopg3 driver URL SQLAlchemy expects; leave everything else as-is."""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'budgeteer.db')}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB - generous for a bank statement PDF

    # Domain-level defaults
    CURRENCY_SYMBOL = "R"
    CURRENCY_CODE = "ZAR"


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


class CSRFTestConfig(TestConfig):
    """Same as TestConfig, but with CSRF protection actually turned on -
    used by tests/test_csrf.py to catch forms that forget the token
    (WTF_CSRF_ENABLED = False elsewhere makes that bug invisible)."""

    WTF_CSRF_ENABLED = True
