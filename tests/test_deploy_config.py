import pytest

from config import _normalize_db_url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        (
            "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require",
            "postgresql+psycopg://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require",
        ),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///budgeteer.db", "sqlite:///budgeteer.db"),
    ],
)
def test_normalize_db_url(url, expected):
    assert _normalize_db_url(url) == expected


def test_healthz_is_public(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data == b"ok"
