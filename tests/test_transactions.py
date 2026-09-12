from datetime import date

from tests.conftest import login
from app.models import Transaction


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
