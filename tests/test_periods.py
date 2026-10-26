from datetime import date

import pytest

from tests.conftest import login
from app.models import Transaction
from app.models.opening_balance import MonthlyOpeningBalance
from app.utils.periods import Period, period_containing, recent_cycles, resolve_period


# --- Period math ---

@pytest.mark.parametrize(
    "day, start_day, expected",
    [
        (date(2026, 10, 15), 1, (date(2026, 10, 1), date(2026, 10, 31))),
        (date(2026, 10, 3), 25, (date(2026, 9, 25), date(2026, 10, 24))),
        (date(2026, 10, 25), 25, (date(2026, 10, 25), date(2026, 11, 24))),
        (date(2027, 1, 10), 25, (date(2026, 12, 25), date(2027, 1, 24))),
        (date(2026, 3, 1), 28, (date(2026, 2, 28), date(2026, 3, 27))),
    ],
)
def test_period_containing(day, start_day, expected):
    period = period_containing(day, start_day)
    assert (period.start, period.end) == expected
    assert period.is_cycle


def test_labels():
    assert period_containing(date(2026, 10, 15)).label == "October 2026"
    assert period_containing(date(2026, 10, 3), 25).label == "25 Sep – 24 Oct 2026"
    assert Period(date(2026, 12, 25), date(2027, 1, 24), 25).label == "25 Dec 2026 – 24 Jan 2027"


def test_shifting_steps_by_cycle_or_by_custom_length():
    payday = period_containing(date(2026, 10, 3), 25)
    assert payday.shifted(1) == Period(date(2026, 10, 25), date(2026, 11, 24), 25)
    assert payday.shifted(-1) == Period(date(2026, 8, 25), date(2026, 9, 24), 25)

    fortnight = Period(date(2026, 10, 1), date(2026, 10, 14))
    assert fortnight.shifted(1) == Period(date(2026, 10, 15), date(2026, 10, 28))


def test_budget_factor():
    assert period_containing(date(2026, 2, 10)).budget_factor == 1  # short month is still one budget
    assert Period(date(2026, 9, 25), date(2026, 12, 24), 25).budget_factor == 3
    assert Period(date(2026, 10, 1), date(2026, 10, 14)).budget_factor == pytest.approx(14 / 30.4375)


def test_recent_cycles_end_with_selected_period():
    cycles = recent_cycles(period_containing(date(2026, 10, 3), 25), 3)
    assert [c.start for c in cycles] == [date(2026, 7, 25), date(2026, 8, 25), date(2026, 9, 25)]


def test_resolve_period():
    today = date(2026, 10, 26)
    assert resolve_period({}, 25, today) == Period(date(2026, 10, 25), date(2026, 11, 24), 25)
    custom = resolve_period({"start": "2026-09-25", "end": "2026-10-24"}, 1, today)
    assert (custom.start, custom.end) == (date(2026, 9, 25), date(2026, 10, 24))
    # Reversed dates are swapped rather than rejected.
    assert resolve_period({"start": "2026-10-24", "end": "2026-09-25"}, 1, today) == custom
    assert resolve_period({"month": "2026-03"}, 1, today) == Period(date(2026, 3, 1), date(2026, 3, 31))
    # Garbage falls back to the current period.
    assert resolve_period({"start": "nope", "month": "x"}, 1, today) == period_containing(today)


# --- Pages ---

def _txn(db, household, user, category, ttype, amount, day, description=None):
    db.session.add(Transaction(household_id=household.id, user_id=user.id, category_id=category.id,
                               type=ttype, amount=amount, date=day, description=description))
    db.session.commit()


def test_dashboard_custom_range_puts_payday_and_bills_together(client, db, household, member_user, salary_category, groceries_category):
    _txn(db, household, member_user, salary_category, "income", 30000, date(2026, 9, 25))
    _txn(db, household, member_user, groceries_category, "expense", 4321, date(2026, 10, 1))
    _txn(db, household, member_user, groceries_category, "expense", 999, date(2026, 10, 25))  # next period
    login(client, member_user.email)

    html = client.get("/?start=2026-09-25&end=2026-10-24").get_data(as_text=True)
    assert "25 Sep – 24 Oct 2026" in html
    assert "30,000.00" in html
    assert "4,321.00" in html
    assert "25,679.00" in html  # net cash flow: the 25 Oct expense is outside the range


def test_household_start_day_sets_default_period(client, db, household, admin_user, groceries_category):
    login(client, admin_user.email)
    resp = client.post("/admin/household", data={"name": "Test Household", "period_start_day": "25"},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert household.period_start_day == 25

    expected = period_containing(date.today(), 25)
    html = client.get("/transactions/").get_data(as_text=True)
    assert expected.label in html


def test_household_start_day_must_exist_in_every_month(client, household, admin_user):
    login(client, admin_user.email)
    client.post("/admin/household", data={"name": "Test Household", "period_start_day": "31"})
    assert household.period_start_day == 1


def test_household_settings_are_admin_only(client, member_user):
    login(client, member_user.email)
    assert client.get("/admin/household").status_code == 403


def test_transactions_custom_range_and_filters(client, db, household, member_user, groceries_category):
    _txn(db, household, member_user, groceries_category, "expense", 10, date(2026, 9, 24), "Before range")
    _txn(db, household, member_user, groceries_category, "expense", 20, date(2026, 9, 25), "First day")
    _txn(db, household, member_user, groceries_category, "expense", 30, date(2026, 10, 24), "Last day")
    _txn(db, household, member_user, groceries_category, "expense", 40, date(2026, 10, 25), "After range")
    login(client, member_user.email)

    html = client.get(
        f"/transactions/?start=2026-09-25&end=2026-10-24&category_id={groceries_category.id}"
    ).get_data(as_text=True)
    assert "First day" in html and "Last day" in html
    assert "Before range" not in html and "After range" not in html
    # The next arrow steps by the range's own length (30 days) and keeps the category filter.
    assert f"category_id={groceries_category.id}&amp;start=2026-10-25&amp;end=2026-11-23" in html


def test_opening_balance_override_at_a_payday_period_start(client, db, household, member_user):
    household.period_start_day = 25
    db.session.commit()
    login(client, member_user.email)

    client.post("/transactions/opening-balance",
                data={"start": "2026-09-25", "end": "2026-10-24", "amount": "1234.00"})
    assert MonthlyOpeningBalance.query.filter_by(household_id=household.id, month=date(2026, 9, 25)).one()

    html = client.get("/transactions/?start=2026-09-25&end=2026-10-24").get_data(as_text=True)
    assert "1,234.00" in html
