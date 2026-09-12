"""Regression coverage for the "CSRF token is missing" bug.

Every other test module runs with WTF_CSRF_ENABLED = False (via TestConfig)
for convenience, which means a template that forgets to include a CSRF
token would pass the rest of the suite and still 400 in production. These
tests use CSRFTestConfig (CSRF genuinely enabled) so that class of bug
can't slip through silently again.
"""

import glob
import re

from app.extensions import db
from app.models.category import TYPE_INCOME
from app.models.wishlist import WishlistItem
from tests.conftest import extract_csrf_token, login_with_csrf


def test_every_rendered_post_form_includes_a_csrf_token():
    """Static scan: any `<form method="post">` in the templates must carry
    either `form.hidden_tag()` or an explicit csrf_token input."""
    offenders = []
    for path in glob.glob("app/templates/**/*.html", recursive=True):
        text = open(path, encoding="utf-8").read()
        for i, form in enumerate(re.findall(r'<form method="post".*?</form>', text, re.S)):
            if "csrf_token" not in form and "hidden_tag" not in form:
                offenders.append(f"{path} (form #{i})")
    assert not offenders, f"POST forms missing a CSRF token: {offenders}"


def test_deleting_a_wishlist_item_succeeds_with_csrf_enabled(csrf_app, csrf_client, csrf_db):
    from app.models import Household, User
    from app.models.user import ROLE_MEMBER

    household = Household(name="CSRF Test Household")
    csrf_db.session.add(household)
    csrf_db.session.commit()

    user = User(household_id=household.id, email="csrf@example.com", display_name="CSRF Tester", role=ROLE_MEMBER)
    user.set_password("password123")
    csrf_db.session.add(user)
    csrf_db.session.commit()

    login_with_csrf(csrf_client, "csrf@example.com")

    item = WishlistItem(household_id=household.id, created_by_id=user.id, name="Bug bounty couch", estimated_cost=1000)
    csrf_db.session.add(item)
    csrf_db.session.commit()

    page = csrf_client.get("/wishlist/")
    assert page.status_code == 200
    token = extract_csrf_token(page.get_data(as_text=True))

    resp = csrf_client.post(f"/wishlist/{item.id}/delete", data={"csrf_token": token}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"The CSRF token is missing" not in resp.data
    assert db.session.get(WishlistItem, item.id) is None


def test_deleting_without_a_csrf_token_is_rejected(csrf_app, csrf_client, csrf_db):
    """Sanity check the other way: CSRFTestConfig genuinely enforces the
    token, so the two tests above aren't passing by accident."""
    from app.models import Household, User
    from app.models.user import ROLE_MEMBER

    household = Household(name="CSRF Reject Household")
    csrf_db.session.add(household)
    csrf_db.session.commit()
    user = User(household_id=household.id, email="reject@example.com", display_name="Reject Tester", role=ROLE_MEMBER)
    user.set_password("password123")
    csrf_db.session.add(user)
    csrf_db.session.commit()
    login_with_csrf(csrf_client, "reject@example.com")

    item = WishlistItem(household_id=household.id, created_by_id=user.id, name="Should survive", estimated_cost=500)
    csrf_db.session.add(item)
    csrf_db.session.commit()

    resp = csrf_client.post(f"/wishlist/{item.id}/delete", data={})
    assert resp.status_code == 400
    assert db.session.get(WishlistItem, item.id) is not None
