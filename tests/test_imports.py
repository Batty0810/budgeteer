from datetime import date
from io import BytesIO

from app.extensions import db
from app.models import Transaction, RecurringItem
from app.models.statement_import import StatementImport
from app.models.opening_balance import MonthlyOpeningBalance
from tests.conftest import login
from tests.pdf_helpers import build_statement_pdf, SAMPLE_STATEMENT_LINES


def _upload(client, lines=SAMPLE_STATEMENT_LINES, password=""):
    data = {
        "statement": (BytesIO(build_statement_pdf(lines)), "statement.pdf"),
        "password": password,
    }
    return client.post("/imports/upload", data=data, content_type="multipart/form-data", follow_redirects=True)


def test_uploading_a_statement_stages_rows_for_review(client, member_user, salary_category, groceries_category):
    login(client, member_user.email)
    resp = _upload(client)
    assert resp.status_code == 200
    assert b"Review before importing" in resp.data
    assert b"SALARY - ACME CORP" in resp.data
    assert b"450.25" in resp.data

    statement_import = StatementImport.query.first()
    assert statement_import is not None
    assert len(statement_import.rows) == 5
    # Salary line should be pre-guessed against the household's own category.
    salary_row = next(r for r in statement_import.rows if "SALARY" in r.description)
    assert salary_row.category_id == salary_category.id


def test_rejecting_a_non_pdf_upload(client, member_user):
    login(client, member_user.email)
    data = {"statement": (BytesIO(b"not a pdf"), "statement.txt"), "password": ""}
    resp = client.post("/imports/upload", data=data, content_type="multipart/form-data")
    assert b"PDF files only" in resp.data
    assert StatementImport.query.count() == 0


def test_confirming_an_import_creates_real_transactions(client, member_user, salary_category, groceries_category, household):
    login(client, member_user.email)
    _upload(client)
    statement_import = StatementImport.query.first()
    row_ids = [r.id for r in statement_import.rows]

    form_data = {}
    for row in statement_import.rows:
        prefix = f"row-{row.id}"
        form_data[f"{prefix}-include"] = "on"
        form_data[f"{prefix}-date"] = row.date.isoformat()
        form_data[f"{prefix}-description"] = row.description
        form_data[f"{prefix}-type"] = row.type
        form_data[f"{prefix}-amount"] = str(row.amount)
        # Only the salary row has a guessed category by default in this test;
        # explicitly assign the others so nothing gets silently skipped.
        form_data[f"{prefix}-category_id"] = str(row.category_id or groceries_category.id)

    # Mark the salary row as recurring, monthly.
    salary_row = next(r for r in statement_import.rows if "SALARY" in r.description)
    form_data[f"row-{salary_row.id}-is_recurring"] = "on"
    form_data[f"row-{salary_row.id}-recurring_frequency"] = "monthly"

    resp = client.post(f"/imports/{statement_import.id}/confirm", data=form_data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Imported 5 transaction" in resp.data

    assert Transaction.query.count() == 5
    assert RecurringItem.query.count() == 1
    recurring = RecurringItem.query.first()
    assert recurring.frequency == "monthly"
    assert recurring.amount == salary_row.amount

    # Staging rows are gone once confirmed.
    assert StatementImport.query.count() == 0
    assert db.session.get(StatementImport, statement_import.id) is None


def test_rows_left_unticked_are_not_imported(client, member_user, groceries_category):
    login(client, member_user.email)
    _upload(client)
    statement_import = StatementImport.query.first()

    form_data = {}
    for i, row in enumerate(statement_import.rows):
        prefix = f"row-{row.id}"
        if i == 0:
            form_data[f"{prefix}-include"] = "on"  # only the first row is ticked
        form_data[f"{prefix}-date"] = row.date.isoformat()
        form_data[f"{prefix}-description"] = row.description
        form_data[f"{prefix}-type"] = row.type
        form_data[f"{prefix}-amount"] = str(row.amount)
        form_data[f"{prefix}-category_id"] = str(groceries_category.id)

    client.post(f"/imports/{statement_import.id}/confirm", data=form_data, follow_redirects=True)
    assert Transaction.query.count() == 1


def test_rows_with_no_category_chosen_are_skipped_not_imported_blank(client, member_user):
    login(client, member_user.email)
    _upload(client)
    statement_import = StatementImport.query.first()

    form_data = {}
    for row in statement_import.rows:
        prefix = f"row-{row.id}"
        form_data[f"{prefix}-include"] = "on"
        form_data[f"{prefix}-date"] = row.date.isoformat()
        form_data[f"{prefix}-description"] = row.description
        form_data[f"{prefix}-type"] = row.type
        form_data[f"{prefix}-amount"] = str(row.amount)
        form_data[f"{prefix}-category_id"] = ""  # nobody picked a category

    resp = client.post(f"/imports/{statement_import.id}/confirm", data=form_data, follow_redirects=True)
    assert Transaction.query.count() == 0
    assert b"Skipped 5 row" in resp.data


def test_a_category_id_from_another_household_is_rejected(client, member_user, admin_user, household):
    """admin_user's fixture household differs from member_user's - use its
    category id as an attempted cross-household injection."""
    from app.models import Category
    from app.models.category import TYPE_EXPENSE

    other_household_category = Category(household_id=999999, name="Not yours", type=TYPE_EXPENSE, color="#000000")
    db.session.add(other_household_category)
    db.session.commit()

    login(client, member_user.email)
    _upload(client)
    statement_import = StatementImport.query.first()
    row = statement_import.rows[0]

    resp = client.post(
        f"/imports/{statement_import.id}/confirm",
        data={
            f"row-{row.id}-include": "on",
            f"row-{row.id}-date": row.date.isoformat(),
            f"row-{row.id}-description": row.description,
            f"row-{row.id}-type": row.type,
            f"row-{row.id}-amount": str(row.amount),
            f"row-{row.id}-category_id": str(other_household_category.id),
        },
        follow_redirects=True,
    )
    assert Transaction.query.count() == 0
    assert b"Skipped 1 row" in resp.data


def test_cancelling_an_import_discards_it(client, member_user):
    login(client, member_user.email)
    _upload(client)
    statement_import = StatementImport.query.first()

    resp = client.post(f"/imports/{statement_import.id}/cancel", follow_redirects=True)
    assert resp.status_code == 200
    assert StatementImport.query.count() == 0
    assert Transaction.query.count() == 0


def test_applying_the_opening_balance_override(client, member_user, groceries_category):
    login(client, member_user.email)
    _upload(client)
    statement_import = StatementImport.query.first()

    form_data = {"apply_opening_balance": "on"}
    for row in statement_import.rows:
        prefix = f"row-{row.id}"
        form_data[f"{prefix}-date"] = row.date.isoformat()
        form_data[f"{prefix}-description"] = row.description
        form_data[f"{prefix}-type"] = row.type
        form_data[f"{prefix}-amount"] = str(row.amount)
        form_data[f"{prefix}-category_id"] = str(groceries_category.id)
        # deliberately leave "include" off every row - only checking the balance override here

    client.post(f"/imports/{statement_import.id}/confirm", data=form_data, follow_redirects=True)
    override = MonthlyOpeningBalance.query.filter_by(household_id=member_user.household_id, month=date(2026, 8, 1)).first()
    assert override is not None
    assert override.amount == statement_import.opening_balance_guess


def test_an_import_belonging_to_another_household_is_not_reachable(client, member_user):
    other = StatementImport(household_id=999999, uploaded_by_id=member_user.id, filename="x.pdf")
    db.session.add(other)
    db.session.commit()

    login(client, member_user.email)
    resp = client.get(f"/imports/{other.id}/review")
    assert resp.status_code == 404
