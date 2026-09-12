from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.account import BankAccount
from app.models.category import Category
from app.models.recurring import RecurringItem
from app.models.transaction import Transaction
from app.utils.forecasting import project_cash_flow
from app.blueprints.forecast.forms import AccountForm, RecurringItemForm

bp = Blueprint("forecast", __name__, url_prefix="/forecast")


def _get_or_create_account():
    account = BankAccount.query.filter_by(household_id=current_user.household_id).first()
    if account is None:
        account = BankAccount(household_id=current_user.household_id, name="Main Account", starting_balance=0, as_of_date=date.today())
        db.session.add(account)
        db.session.commit()
    return account


def _populate_category_choices(form, include_category=None):
    categories = (
        Category.query.filter_by(household_id=current_user.household_id, is_archived=False)
        .order_by(Category.name.asc())
        .all()
    )
    # Keep a since-archived category selectable when editing a recurring item
    # that still points at it, so the form doesn't reject its own value.
    if include_category and include_category.is_archived and include_category not in categories:
        categories = categories + [include_category]
    form.category_id.choices = [
        (c.id, c.name + (" - archived" if c.is_archived else "")) for c in categories
    ]


@bp.route("/")
@login_required
def index():
    months = request.args.get("months", default=3, type=int)
    months = months if months in (3, 6, 12) else 3

    account = _get_or_create_account()
    future_transactions = Transaction.query.filter(
        Transaction.household_id == current_user.household_id,
        Transaction.date > date.today(),
    ).all()

    timeline = project_cash_flow(
        household=current_user.household,
        months=months,
        starting_balance=account.starting_balance,
        starting_date=max(account.as_of_date, date.today()),
        future_transactions=future_transactions,
    )

    lowest_point = min(timeline, key=lambda d: d["balance"]) if timeline else None

    # A monthly checkpoint (balance on the 1st of each month) for the table-view
    # fallback - the daily timeline is too long to read as a table.
    monthly_checkpoints = [day for day in timeline if day["date"].day == 1]
    if timeline and (not monthly_checkpoints or monthly_checkpoints[0]["date"] != timeline[0]["date"]):
        monthly_checkpoints.insert(0, timeline[0])

    recurring_items = (
        RecurringItem.query.filter_by(household_id=current_user.household_id, is_active=True)
        .order_by(RecurringItem.name.asc())
        .all()
    )

    return render_template(
        "forecast/index.html",
        account=account,
        timeline=timeline,
        lowest_point=lowest_point,
        monthly_checkpoints=monthly_checkpoints,
        months=months,
        recurring_items=recurring_items,
    )


@bp.route("/account", methods=["GET", "POST"])
@login_required
def edit_account():
    account = _get_or_create_account()
    form = AccountForm(obj=account)
    if form.validate_on_submit():
        account.name = form.name.data.strip()
        account.starting_balance = form.starting_balance.data
        account.as_of_date = form.as_of_date.data
        db.session.commit()
        flash("Account balance updated.", "success")
        return redirect(url_for("forecast.index"))
    return render_template("forecast/account_form.html", form=form)


@bp.route("/recurring/new", methods=["GET", "POST"])
@login_required
def new_recurring():
    form = RecurringItemForm()
    _populate_category_choices(form)
    if request.method == "GET":
        form.start_date.data = date.today()
    if form.validate_on_submit():
        item = RecurringItem(
            household_id=current_user.household_id,
            category_id=form.category_id.data,
            name=form.name.data.strip(),
            type=form.type.data,
            amount=form.amount.data,
            frequency=form.frequency.data,
            start_date=form.start_date.data,
        )
        db.session.add(item)
        db.session.commit()
        flash(f"Added recurring item {item.name!r}.", "success")
        return redirect(url_for("forecast.index"))
    return render_template("forecast/recurring_form.html", form=form, mode="new")


@bp.route("/recurring/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recurring(item_id):
    item = db.session.get(RecurringItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    form = RecurringItemForm(obj=item)
    _populate_category_choices(form, include_category=item.category)
    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.category_id = form.category_id.data
        item.type = form.type.data
        item.amount = form.amount.data
        item.frequency = form.frequency.data
        item.start_date = form.start_date.data
        db.session.commit()
        flash(f"Updated {item.name!r}.", "success")
        return redirect(url_for("forecast.index"))
    return render_template("forecast/recurring_form.html", form=form, mode="edit", item=item)


@bp.route("/recurring/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_recurring(item_id):
    item = db.session.get(RecurringItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Recurring item removed.", "info")
    return redirect(url_for("forecast.index"))
