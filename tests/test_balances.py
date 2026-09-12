from datetime import date

from app.extensions import db
from app.models.account import BankAccount
from app.models.opening_balance import MonthlyOpeningBalance
from app.models.transaction import Transaction
from app.utils.balances import get_balance_brought_forward, get_month_running_balances
from tests.conftest import login


def _txn(db, household, user, category, txn_type, amount, on_date):
    t = Transaction(
        household_id=household.id,
        user_id=user.id,
        category_id=category.id,
        type=txn_type,
        amount=amount,
        date=on_date,
    )
    db.session.add(t)
    db.session.commit()
    return t


def test_no_account_or_override_defaults_to_zero(household):
    result = get_balance_brought_forward(household, date(2026, 3, 1))
    assert result["amount"] == 0
    assert result["source"] == "none"


def test_rolls_forward_from_the_account_anchor(db, household, member_user, salary_category):
    db.session.add(BankAccount(household_id=household.id, starting_balance=1000, as_of_date=date(2026, 1, 1)))
    db.session.commit()
    _txn(db, household, member_user, salary_category, "income", 500, date(2026, 1, 15))

    result = get_balance_brought_forward(household, date(2026, 2, 1))
    assert result["source"] == "account"
    assert result["amount"] == 1500  # 1000 + 500 income logged in January


def test_rolls_backward_when_the_account_anchor_is_later(db, household, member_user, groceries_category):
    db.session.add(BankAccount(household_id=household.id, starting_balance=2000, as_of_date=date(2026, 3, 1)))
    db.session.commit()
    _txn(db, household, member_user, groceries_category, "expense", 300, date(2026, 2, 10))

    result = get_balance_brought_forward(household, date(2026, 2, 1))
    assert result["amount"] == 2300  # balance before the Feb grocery spend that happened before the anchor


def test_override_takes_precedence_and_future_months_build_on_it(db, household, member_user, salary_category):
    db.session.add(BankAccount(household_id=household.id, starting_balance=999999, as_of_date=date(2026, 1, 1)))
    db.session.add(MonthlyOpeningBalance(household_id=household.id, month=date(2026, 3, 1), amount=5000))
    db.session.commit()
    _txn(db, household, member_user, salary_category, "income", 100, date(2026, 3, 10))

    result = get_balance_brought_forward(household, date(2026, 4, 1))
    assert result["source"] == "override"
    assert result["amount"] == 5100  # anchors to the override, not the wildly-off account balance


def test_running_balances_are_correct_and_ignore_display_filters(db, household, member_user, salary_category, groceries_category):
    db.session.add(BankAccount(household_id=household.id, starting_balance=1000, as_of_date=date(2026, 5, 1)))
    db.session.commit()
    t1 = _txn(db, household, member_user, salary_category, "income", 2000, date(2026, 5, 5))
    t2 = _txn(db, household, member_user, groceries_category, "expense", 300, date(2026, 5, 10))

    opening, balances, closing = get_month_running_balances(household, date(2026, 5, 1), date(2026, 6, 1))
    assert opening["amount"] == 1000
    assert balances[t1.id] == 3000
    assert balances[t2.id] == 2700
    assert closing == 2700


def test_opening_balance_override_flow_via_the_ui(client, member_user, groceries_category, db):
    db.session.add(BankAccount(household_id=member_user.household_id, starting_balance=1000, as_of_date=date(2026, 1, 1)))
    db.session.commit()
    login(client, member_user.email)

    resp = client.post(
        "/transactions/opening-balance",
        data={"month": "2026-03", "amount": "4200.00", "note": "per bank statement"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp = client.get("/transactions/?month=2026-03")
    assert b"4,200.00" in resp.data

    resp = client.post("/transactions/opening-balance/clear", data={"month": "2026-03"}, follow_redirects=True)
    assert resp.status_code == 200
    assert MonthlyOpeningBalance.query.filter_by(household_id=member_user.household_id, month=date(2026, 3, 1)).first() is None
