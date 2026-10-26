import os
from datetime import timedelta

from sqlalchemy.pool import StaticPool

basedir = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url):
    """Hosted Postgres URLs (Neon, Heroku, ...) use 'postgres://' or a bare
    'postgresql://' scheme. SQLAlchemy 2.x rejects the former and maps the
    latter to psycopg2, which isn't installed. Rewrite both to the psycopg3
    driver URL; leave everything else (e.g. sqlite) as-is."""
    if url:
        for scheme in ("postgres://", "postgresql://"):
            if url.startswith(scheme):
                return url.replace(scheme, "postgresql+psycopg://", 1)
    return url


_DATABASE_URL = _normalize_db_url(
    os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'budgeteer.db')}")
)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = _DATABASE_URL
    # Neon suspends idle databases and drops their connections; check each
    # pooled connection before use and recycle them well inside that window.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_recycle": 280} if _DATABASE_URL.startswith("postgresql") else {}
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    # Render serves the app over HTTPS only (it sets RENDER=true); keep
    # login cookies off plain HTTP there, but not in local dev.
    SESSION_COOKIE_SECURE = REMEMBER_COOKIE_SECURE = bool(os.environ.get("RENDER"))
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
