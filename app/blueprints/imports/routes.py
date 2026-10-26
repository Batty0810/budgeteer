from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.category import Category
from app.models.opening_balance import MonthlyOpeningBalance
from app.models.recurring import RecurringItem, FREQUENCY_CHOICES, FREQ_MONTHLY
from app.models.statement_import import StatementImport, StatementImportRow
from app.models.transaction import Transaction
from app.utils.statement_parser import parse_pdf_statement, StatementParseError
from app.blueprints.imports.forms import UploadStatementForm

bp = Blueprint("imports", __name__, url_prefix="/imports")


def _household_categories():
    return (
        Category.query.filter_by(household_id=current_user.household_id, is_archived=False)
        .order_by(Category.type.asc(), Category.name.asc())
        .all()
    )


def _get_import_or_404(import_id):
    statement_import = db.session.get(StatementImport, import_id)
    if statement_import is None or statement_import.household_id != current_user.household_id:
        abort(404)
    return statement_import


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = UploadStatementForm()
    if form.validate_on_submit():
        file = form.statement.data
        file_bytes = file.read()
        categories = _household_categories()
        try:
            result = parse_pdf_statement(file_bytes, password=form.password.data or None, categories=categories)
        except StatementParseError as exc:
            flash(
                f"Couldn't read that PDF ({exc}). If it's password-protected, enter the password above and try again.",
                "error",
            )
            return render_template("imports/upload.html", form=form)

        if not result["rows"]:
            flash(
                "No transactions were recognised in that PDF - the layout may not be one Budgeteer understands yet. "
                "You can still log entries manually.",
                "error",
            )
            return render_template("imports/upload.html", form=form)

        statement_import = StatementImport(
            household_id=current_user.household_id,
            uploaded_by_id=current_user.id,
            filename=file.filename or "statement.pdf",
            opening_balance_guess=result["opening_balance"],
            closing_balance_guess=result["closing_balance"],
            statement_month_guess=result["statement_month"],
        )
        db.session.add(statement_import)
        db.session.flush()

        for row in result["rows"]:
            db.session.add(
                StatementImportRow(
                    import_id=statement_import.id,
                    date=row["date"],
                    description=row["description"],
                    amount=row["amount"],
                    type=row["type"],
                    category_id=row["category_id"],
                    raw_line=row["raw_line"],
                )
            )
        db.session.commit()
        flash(f"Found {len(result['rows'])} possible transactions. Review them below before importing anything.", "success")
        return redirect(url_for("imports.review", import_id=statement_import.id))

    return render_template("imports/upload.html", form=form)


@bp.route("/<int:import_id>/review")
@login_required
def review(import_id):
    statement_import = _get_import_or_404(import_id)
    return render_template(
        "imports/review.html",
        statement_import=statement_import,
        categories=_household_categories(),
        frequency_choices=FREQUENCY_CHOICES,
        default_frequency=FREQ_MONTHLY,
    )


@bp.route("/<int:import_id>/confirm", methods=["POST"])
@login_required
def confirm(import_id):
    statement_import = _get_import_or_404(import_id)
    valid_category_ids = {c.id for c in _household_categories()}

    imported_count = 0
    recurring_count = 0
    skipped_no_category = 0

    for row in statement_import.rows:
        prefix = f"row-{row.id}"
        if request.form.get(f"{prefix}-include") != "on":
            continue

        category_id = request.form.get(f"{prefix}-category_id", type=int)
        if category_id not in valid_category_ids:
            skipped_no_category += 1
            continue

        try:
            row_date = date.fromisoformat(request.form.get(f"{prefix}-date", ""))
        except ValueError:
            row_date = row.date
        row_type = request.form.get(f"{prefix}-type") or row.type
        if row_type not in ("income", "expense"):
            row_type = row.type
        row_description = (request.form.get(f"{prefix}-description") or row.description).strip()
        try:
            amount = Decimal(request.form.get(f"{prefix}-amount", "") or str(row.amount))
        except InvalidOperation:
            amount = row.amount
        if amount <= 0:
            continue  # nonsensical amount - skip rather than write a zero/negative transaction

        db.session.add(
            Transaction(
                household_id=current_user.household_id,
                user_id=current_user.id,
                category_id=category_id,
                type=row_type,
                amount=amount,
                description=row_description,
                date=row_date,
            )
        )
        imported_count += 1

        if request.form.get(f"{prefix}-is_recurring") == "on":
            frequency = request.form.get(f"{prefix}-recurring_frequency") or FREQ_MONTHLY
            valid_frequencies = {choice[0] for choice in FREQUENCY_CHOICES}
            if frequency not in valid_frequencies:
                frequency = FREQ_MONTHLY
            db.session.add(
                RecurringItem(
                    household_id=current_user.household_id,
                    category_id=category_id,
                    user_id=current_user.id,
                    name=row_description[:120] or "Imported recurring item",
                    type=row_type,
                    amount=amount,
                    frequency=frequency,
                    start_date=row_date,
                )
            )
            recurring_count += 1

    if (
        request.form.get("apply_opening_balance") == "on"
        and statement_import.opening_balance_guess is not None
        and statement_import.statement_month_guess
    ):
        month_start = statement_import.statement_month_guess
        override = MonthlyOpeningBalance.query.filter_by(
            household_id=current_user.household_id, month=month_start
        ).first()
        if override is None:
            override = MonthlyOpeningBalance(household_id=current_user.household_id, month=month_start)
            db.session.add(override)
        override.amount = statement_import.opening_balance_guess
        override.note = f"From statement: {statement_import.filename}"

    db.session.delete(statement_import)
    db.session.commit()

    message = f"Imported {imported_count} transaction(s)"
    if recurring_count:
        message += f", {recurring_count} set up as recurring"
    if skipped_no_category:
        message += f". Skipped {skipped_no_category} row(s) with no category chosen"
    flash(message + ".", "success" if imported_count else "info")
    return redirect(url_for("transactions.list_transactions"))


@bp.route("/<int:import_id>/cancel", methods=["POST"])
@login_required
def cancel(import_id):
    statement_import = _get_import_or_404(import_id)
    db.session.delete(statement_import)
    db.session.commit()
    flash("Import discarded - nothing was added to your ledger.", "info")
    return redirect(url_for("imports.upload"))
