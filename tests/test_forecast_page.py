from datetime import date, timedelta

from tests.conftest import login
from app.models import RecurringItem, Transaction, User
from app.models.account import BankAccount
from app.models.user import ROLE_MEMBER


def _setup(db, household, member_user, salary_category, groceries_category):
    """Mel earns a salary, Pat pays for streaming, and rent is shared."""
    partner = User(household_id=household.id, email="pat@example.com", display_name="Pat Partner", role=ROLE_MEMBER)
    partner.set_password("password123")
    db.session.add(partner)
    db.session.add(BankAccount(household_id=household.id, name="Main", starting_balance=1000, as_of_date=date.today()))
    soon = date.today() + timedelta(days=5)
    db.session.flush()
    db.session.add_all([
        RecurringItem(household_id=household.id, category_id=salary_category.id, user_id=member_user.id,
                      name="Mel salary", type="income", amount=20000, start_date=soon),
        RecurringItem(household_id=household.id, category_id=groceries_category.id, user_id=partner.id,
                      name="Pat streaming", type="expense", amount=200, start_date=soon),
        RecurringItem(household_id=household.id, category_id=groceries_category.id, user_id=None,
                      name="Shared rent", type="expense", amount=8000, start_date=soon),
    ])
    db.session.commit()
    return partner


def test_forecast_offers_one_month(client, db, household, member_user, salary_category, groceries_category):
    _setup(db, household, member_user, salary_category, groceries_category)
    login(client, member_user.email)
    html = client.get("/forecast/?months=1").get_data(as_text=True)
    assert "1 month" in html
    assert "Projected in 1 month" in html
    # 1,000 + 20,000 - 200 - 8,000, all landing within the next month
    assert "12,800.00" in html


def test_forecast_everyone_view_lists_upcoming_income_and_expenses(client, db, household, member_user, salary_category, groceries_category):
    _setup(db, household, member_user, salary_category, groceries_category)
    login(client, member_user.email)
    html = client.get("/forecast/?months=1").get_data(as_text=True)
    assert "Upcoming" in html
    for name in ("Mel salary", "Pat streaming", "Shared rent"):
        assert name in html
    assert "20,000.00" in html  # coming in
    assert "8,200.00" in html  # going out


def test_forecast_filtered_to_one_person(client, db, household, member_user, salary_category, groceries_category):
    partner = _setup(db, household, member_user, salary_category, groceries_category)
    login(client, member_user.email)

    html = client.get(f"/forecast/?months=1&who={partner.id}").get_data(as_text=True)
    assert "Pat streaming" in html
    assert "Mel salary" not in html and "Shared rent" not in html
    assert "Pat Partner&#39;s income &amp; expenses" in html
    assert "-R 200.00" in html  # running total from R 0, not the bank balance

    html = client.get("/forecast/?months=1&who=shared").get_data(as_text=True)
    assert "Shared rent" in html and "Pat streaming" not in html


def test_forecast_income_only(client, db, household, member_user, salary_category, groceries_category):
    _setup(db, household, member_user, salary_category, groceries_category)
    login(client, member_user.email)
    html = client.get("/forecast/?months=1&type=income").get_data(as_text=True)
    assert "Mel salary" in html
    assert "Pat streaming" not in html and "Shared rent" not in html


def test_future_transactions_follow_the_person_filter(client, db, household, member_user, salary_category, groceries_category):
    partner = _setup(db, household, member_user, salary_category, groceries_category)
    db.session.add(Transaction(household_id=household.id, user_id=member_user.id, category_id=groceries_category.id,
                               type="expense", amount=750, description="Mel's dentist",
                               date=date.today() + timedelta(days=3)))
    db.session.commit()
    login(client, member_user.email)
    assert "Mel&#39;s dentist" in client.get(f"/forecast/?who={member_user.id}").get_data(as_text=True)
    assert "Mel&#39;s dentist" not in client.get(f"/forecast/?who={partner.id}").get_data(as_text=True)


def test_recurring_item_owner_can_be_set_and_defaults_to_you(client, db, household, member_user, salary_category):
    login(client, member_user.email)
    html = client.get("/forecast/recurring/new").get_data(as_text=True)
    assert f'<option selected value="{member_user.id}">' in html or f'value="{member_user.id}" selected' in html

    data = {"name": "Rent", "type": "expense", "category_id": salary_category.id, "owner_id": "0",
            "amount": "8000", "frequency": "monthly", "start_date": "2026-11-01"}
    client.post("/forecast/recurring/new", data=data)
    item = RecurringItem.query.one()
    assert item.user_id is None  # shared

    client.post(f"/forecast/recurring/{item.id}/edit", data=dict(data, owner_id=str(member_user.id)))
    assert db.session.get(RecurringItem, item.id).user_id == member_user.id


def test_recurring_from_a_transaction_belongs_to_whoever_logged_it(client, member_user, salary_category):
    login(client, member_user.email)
    client.post("/transactions/new", data={"type": "income", "category_id": salary_category.id, "amount": "5000",
                                           "date": "2026-09-25", "description": "Salary", "tags": "",
                                           "is_recurring": "y", "frequency": "monthly"})
    assert RecurringItem.query.one().user_id == member_user.id
