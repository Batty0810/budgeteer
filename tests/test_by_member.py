from datetime import date

from tests.conftest import login
from app.extensions import db
from app.models import Transaction, User
from app.models.user import ROLE_MEMBER


def _second_member(db, household):
    user = User(household_id=household.id, email="partner@example.com", display_name="Pat Partner", role=ROLE_MEMBER)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


def test_dashboard_breaks_down_income_and_expense_by_member(client, db, household, member_user, salary_category, groceries_category):
    partner = _second_member(db, household)

    db.session.add(Transaction(household_id=household.id, user_id=member_user.id, category_id=salary_category.id,
                                type="income", amount=10000, date=date.today()))
    db.session.add(Transaction(household_id=household.id, user_id=partner.id, category_id=groceries_category.id,
                                type="expense", amount=250, date=date.today()))
    db.session.commit()

    login(client, member_user.email)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"By household member" in resp.data
    assert b"Mel Member" in resp.data
    assert b"Pat Partner" in resp.data
    # Both members' figures appear, including the one who logged nothing of one type.
    assert b"10,000.00" in resp.data
    assert b"250.00" in resp.data


def test_transactions_list_can_be_filtered_by_who_logged_them(client, db, household, member_user, groceries_category):
    partner = _second_member(db, household)
    db.session.add(Transaction(household_id=household.id, user_id=member_user.id, category_id=groceries_category.id,
                                type="expense", amount=100, description="Mel's spend", date=date.today()))
    db.session.add(Transaction(household_id=household.id, user_id=partner.id, category_id=groceries_category.id,
                                type="expense", amount=200, description="Pat's spend", date=date.today()))
    db.session.commit()

    login(client, member_user.email)
    resp = client.get(f"/transactions/?user_id={partner.id}")
    assert resp.status_code == 200
    assert b"Pat&#39;s spend" in resp.data or b"Pat's spend" in resp.data
    assert b"Mel&#39;s spend" not in resp.data and b"Mel's spend" not in resp.data
