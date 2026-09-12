from datetime import date

from app.models.recurring import RecurringItem, FREQ_MONTHLY
from app.models.bill import IrregularBill
from app.utils.forecasting import project_cash_flow, _recurring_occurrences, _bill_occurrences


def _recurring(**overrides):
    defaults = dict(name="Item", type="expense", amount=100, frequency=FREQ_MONTHLY, start_date=date(2026, 1, 1), end_date=None)
    defaults.update(overrides)
    return RecurringItem(**defaults)


def _bill(**overrides):
    defaults = dict(name="Bill", amount=500, due_date=date(2026, 2, 1), recurrence_months=3)
    defaults.update(overrides)
    return IrregularBill(**defaults)


def test_monthly_recurring_occurrences_land_on_the_same_day_each_month():
    item = _recurring(start_date=date(2026, 1, 1))
    occurrences = list(_recurring_occurrences(item, date(2026, 1, 1), date(2026, 3, 31)))
    assert occurrences == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_recurring_occurrences_respect_end_date():
    item = _recurring(start_date=date(2026, 1, 1), end_date=date(2026, 1, 15))
    occurrences = list(_recurring_occurrences(item, date(2026, 1, 1), date(2026, 6, 30)))
    assert occurrences == [date(2026, 1, 1)]


def test_bill_occurrences_repeat_every_recurrence_months():
    bill = _bill(due_date=date(2026, 2, 1), recurrence_months=3)
    occurrences = list(_bill_occurrences(bill, date(2026, 1, 1), date(2026, 12, 31)))
    assert occurrences == [date(2026, 2, 1), date(2026, 5, 1), date(2026, 8, 1), date(2026, 11, 1)]


def test_project_cash_flow_nets_income_expenses_and_bills(household):
    salary = _recurring(name="Salary", type="income", amount=10000, start_date=date(2026, 1, 1))
    rent = _recurring(name="Rent", type="expense", amount=3000, start_date=date(2026, 1, 1))
    bill = _bill(name="Insurance", amount=500, due_date=date(2026, 2, 1), recurrence_months=12)

    timeline = project_cash_flow(
        household=household,
        months=2,
        starting_balance=1000,
        starting_date=date(2026, 1, 1),
        recurring_items=[salary, rent],
        bills=[bill],
        future_transactions=[],
    )

    assert timeline[0]["date"] == date(2026, 1, 1)
    assert timeline[-1]["date"] == date(2026, 3, 1)
    assert len(timeline) == (timeline[-1]["date"] - timeline[0]["date"]).days + 1

    by_date = {row["date"]: row["balance"] for row in timeline}
    assert by_date[date(2026, 1, 1)] == 8000  # 1000 + 10000 - 3000
    assert by_date[date(2026, 2, 1)] == 14500  # 8000 + 10000 - 3000 - 500
    assert by_date[date(2026, 3, 1)] == 21500  # 14500 + 10000 - 3000
