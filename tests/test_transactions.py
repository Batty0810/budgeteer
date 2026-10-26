from datetime import date

from tests.conftest import login
from app.models import Transaction, RecurringItem, User
from app.models.user import ROLE_MEMBER


def test_logging_a_transaction_appears_in_the_list(client, member_user, groceries_category):
    login(client, member_user.email)
    resp = client.post(
        "/transactions/new",
        data={
            "type": "expense",
            "category_id": groceries_category.id,
            "amount": "245.50",
            "date": date.today().isoformat(),
            "description": "Woolworths run",
            "tags": "weekly, essentials",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Woolworths run" in resp.data
    assert b"weekly" in resp.data


def test_editing_a_transaction_with_an_archived_category_does_not_error(client, member_user, groceries_category, db):
    login(client, member_user.email)
    client.post(
        "/transactions/new",
        data={
            "type": "expense",
            "category_id": groceries_category.id,
            "amount": "100.00",
            "date": date.today().isoformat(),
            "description": "Test spend",
            "tags": "",
        },
    )
    txn = Transaction.query.first()
    groceries_category.is_archived = True
    db.session.commit()

    resp = client.get(f"/transactions/{txn.id}/edit")
    assert resp.status_code == 200
    assert b"archived" in resp.data

    resp = client.post(
        f"/transactions/{txn.id}/edit",
        data={
            "type": "expense",
            "category_id": groceries_category.id,
            "amount": "150.00",
            "date": date.today().isoformat(),
            "description": "Updated spend",
            "tags": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Updated spend" in resp.data


def test_transactions_list_can_be_filtered_by_income_or_expense(client, db, household, member_user, salary_category, groceries_category):
    db.session.add(Transaction(household_id=household.id, user_id=member_user.id, category_id=salary_category.id,
                               type="income", amount=5000, description="Pay day", date=date.today()))
    db.session.add(Transaction(household_id=household.id, user_id=member_user.id, category_id=groceries_category.id,
                               type="expense", amount=80, description="Bread and milk", date=date.today()))
    db.session.commit()
    login(client, member_user.email)

    html = client.get("/transactions/?type=expense").get_data(as_text=True)
    assert "Bread and milk" in html and "Pay day" not in html

    html = client.get("/transactions/?type=income").get_data(as_text=True)
    assert "Pay day" in html and "Bread and milk" not in html

    html = client.get("/transactions/").get_data(as_text=True)
    assert "Pay day" in html and "Bread and milk" in html


def _log(client, category, **extra):
    data = {"type": category.type, "category_id": category.id, "amount": "239.00",
            "date": "2026-09-25", "description": "Microsoft 365", "tags": ""}
    data.update(extra)
    return client.post("/transactions/new", data=data, follow_redirects=True)


def test_logging_a_recurring_transaction_adds_it_to_the_forecast(client, db, member_user, groceries_category):
    login(client, member_user.email)
    resp = _log(client, groceries_category, is_recurring="y", frequency="monthly")
    assert b"added to the forecast as recurring" in resp.data

    item = RecurringItem.query.one()
    assert (item.name, item.type, item.amount, item.frequency) == ("Microsoft 365", "expense", 239, "monthly")
    # The logged transaction is the first occurrence; the forecast picks up from the next one.
    assert item.start_date == date(2026, 10, 25)
    txn = Transaction.query.one()
    assert txn.recurring_item_id == item.id

    # Editing it shows "This repeats" already ticked.
    html = client.get(f"/transactions/{txn.id}/edit").get_data(as_text=True)
    assert '<input checked id="is_recurring"' in html

    # Removing the recurring item leaves the transaction in place, just unlinked.
    client.post(f"/forecast/recurring/{item.id}/delete")
    assert db.session.get(Transaction, txn.id).recurring_item_id is None


def test_one_off_transaction_is_not_recurring(client, member_user, groceries_category):
    login(client, member_user.email)
    _log(client, groceries_category, frequency="monthly")
    assert RecurringItem.query.count() == 0
    assert Transaction.query.one().recurring_item_id is None


def test_existing_transaction_can_be_made_recurring_once(client, db, household, member_user, salary_category):
    login(client, member_user.email)
    _log(client, salary_category, description="Nymbis", amount="68737.43")
    txn = Transaction.query.one()
    edit = {"type": "income", "category_id": salary_category.id, "amount": "68737.43",
            "date": "2026-09-25", "description": "Nymbis", "tags": "", "is_recurring": "y", "frequency": "monthly"}
    client.post(f"/transactions/{txn.id}/edit", data=edit)
    client.post(f"/transactions/{txn.id}/edit", data=edit)  # saving again doesn't add a second one
    item = RecurringItem.query.one()
    assert (item.type, item.start_date) == ("income", date(2026, 10, 25))


def _edit(client, txn, category, **overrides):
    data = {"type": category.type, "category_id": category.id, "user_id": txn.user_id, "amount": str(txn.amount),
            "date": txn.date.isoformat(), "description": txn.description or "", "tags": "",
            "is_recurring": "y", "frequency": "monthly"}
    data.update(overrides)
    data = {k: v for k, v in data.items() if v is not None}
    return client.post(f"/transactions/{txn.id}/edit", data=data, follow_redirects=True)


def test_recurring_can_be_changed_turned_off_and_back_on_from_the_transaction(client, db, member_user, groceries_category):
    login(client, member_user.email)
    _log(client, groceries_category, is_recurring="y", frequency="monthly")
    txn = Transaction.query.one()
    item = RecurringItem.query.one()

    _edit(client, txn, groceries_category, frequency="annual", amount="299.00")
    assert (item.frequency, item.amount, item.start_date) == ("annual", 299, date(2027, 9, 25))

    resp = _edit(client, txn, groceries_category, is_recurring=None)
    assert b"taken off the forecast" in resp.data
    assert item.is_active is False
    assert b"Microsoft 365" not in client.get("/forecast/").data

    resp = _edit(client, txn, groceries_category)
    assert b"put back on the forecast" in resp.data
    assert item.is_active is True
    assert RecurringItem.query.count() == 1


def test_editing_unrelated_fields_keeps_forecaster_changes(client, db, member_user, groceries_category):
    login(client, member_user.email)
    _log(client, groceries_category, is_recurring="y", frequency="monthly")
    txn = Transaction.query.one()
    item = RecurringItem.query.one()
    item.amount = 259  # price went up, changed on the Forecaster
    db.session.commit()

    _edit(client, txn, groceries_category, tags="software")
    assert item.amount == 259


def test_transaction_can_be_logged_for_another_member(client, db, household, member_user, salary_category):
    partner = User(household_id=household.id, email="pat@example.com", display_name="Pat Partner", role=ROLE_MEMBER)
    partner.set_password("password123")
    db.session.add(partner)
    db.session.commit()
    login(client, member_user.email)

    html = client.get("/transactions/new").get_data(as_text=True)
    assert "Whose is this?" in html and "Pat Partner" in html

    _log(client, salary_category, user_id=partner.id, is_recurring="y", frequency="monthly")
    assert Transaction.query.one().user_id == partner.id
    assert RecurringItem.query.one().user_id == partner.id

    # Moving it to someone else moves the recurring item with it.
    _edit(client, Transaction.query.one(), salary_category, user_id=member_user.id)
    assert RecurringItem.query.one().user_id == member_user.id
