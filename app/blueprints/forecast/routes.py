from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.account import BankAccount
from app.models.bill import IrregularBill
from app.models.category import Category
from app.models.recurring import RecurringItem
from app.models.transaction import Transaction
from app.models.user import User
from app.utils.forecasting import project_cash_flow
from app.blueprints.forecast.forms import AccountForm, RecurringItemForm

bp = Blueprint("forecast", __name__, url_prefix="/forecast")

HORIZON_CHOICES = (1, 3, 6, 12)
WHO_SHARED = "shared"


def _get_or_create_account():
    account = BankAccount.query.filter_by(household_id=current_user.household_id).first()
    if account is None:
        account = BankAccount(household_id=current_user.household_id, name="Main Account", starting_balance=0, as_of_date=date.today())
        db.session.add(account)
        db.session.commit()
    return account


def _household_users():
    return User.query.filter_by(household_id=current_user.household_id).order_by(User.display_name.asc()).all()


def _populate_owner_choices(form):
    form.owner_id.choices = [(0, "Shared (household)")] + [(u.id, u.display_name) for u in _household_users()]


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
    months = months if months in HORIZON_CHOICES else 3

    # Optional filters: whose items (a user id, or "shared") and which type.
    household_users = _household_users()
    who = request.args.get("who", "")
    owner = next((u for u in household_users if str(u.id) == who), None)
    if who != WHO_SHARED and owner is None:
        who = ""
    txn_type = request.args.get("type", "")
    if txn_type not in ("income", "expense"):
        txn_type = ""
    is_filtered = bool(who or txn_type)

    account = _get_or_create_account()
    today = date.today()

    recurring_items = (
        RecurringItem.query.filter_by(household_id=current_user.household_id, is_active=True)
        .order_by(RecurringItem.type.desc(), RecurringItem.name.asc())
        .all()
    )
    bills = IrregularBill.query.filter_by(household_id=current_user.household_id, is_active=True).all()
    future_transactions = Transaction.query.filter(
        Transaction.household_id == current_user.household_id,
        Transaction.date > today,
    ).all()

    if who == WHO_SHARED:
        recurring_items = [r for r in recurring_items if r.user_id is None]
        future_transactions = []  # every transaction was logged by someone
    elif owner:
        recurring_items = [r for r in recurring_items if r.user_id == owner.id]
        future_transactions = [t for t in future_transactions if t.user_id == owner.id]
        bills = []  # irregular bills are household-wide
    if txn_type:
        recurring_items = [r for r in recurring_items if r.type == txn_type]
        future_transactions = [t for t in future_transactions if t.type == txn_type]
        if txn_type == "income":
            bills = []

    # The bank balance belongs to the whole household, so a filtered view
    # can't start from it - it shows a running total of just those items.
    timeline = project_cash_flow(
        household=current_user.household,
        months=months,
        starting_balance=0 if is_filtered else account.starting_balance,
        starting_date=max(account.as_of_date, today),
        recurring_items=recurring_items,
        bills=bills,
        future_transactions=future_transactions,
    )

    lowest_point = min(timeline, key=lambda d: d["balance"]) if timeline else None
    upcoming = [dict(event, date=day["date"]) for day in timeline for event in day["events"]]
    total_in = sum((e["amount"] for e in upcoming if e["amount"] > 0), 0)
    total_out = -sum((e["amount"] for e in upcoming if e["amount"] < 0), 0)

    # A monthly checkpoint (balance on the 1st of each month) for the table-view
    # fallback - the daily timeline is too long to read as a table.
    monthly_checkpoints = [day for day in timeline if day["date"].day == 1]
    if timeline and (not monthly_checkpoints or monthly_checkpoints[0]["date"] != timeline[0]["date"]):
        monthly_checkpoints.insert(0, timeline[0])

    if who == WHO_SHARED:
        view_label = "Shared"
    elif owner:
        view_label = f"{owner.display_name}'s"
    else:
        view_label = "Everyone's"
    view_label += {"income": " income", "expense": " expenses", "": " income & expenses"}[txn_type]

    return render_template(
        "forecast/index.html",
        account=account,
        timeline=timeline,
        lowest_point=lowest_point,
        monthly_checkpoints=monthly_checkpoints,
        months=months,
        horizon_choices=HORIZON_CHOICES,
        recurring_items=recurring_items,
        upcoming=upcoming,
        total_in=total_in,
        total_out=total_out,
        household_users=household_users,
        selected_who=who,
        selected_type=txn_type,
        is_filtered=is_filtered,
        view_label=view_label,
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
    _populate_owner_choices(form)
    if request.method == "GET":
        form.start_date.data = date.today()
        form.owner_id.data = current_user.id
    if form.validate_on_submit():
        item = RecurringItem(
            household_id=current_user.household_id,
            category_id=form.category_id.data,
            name=form.name.data.strip(),
            type=form.type.data,
            amount=form.amount.data,
            frequency=form.frequency.data,
            start_date=form.start_date.data,
            user_id=form.owner_id.data or None,
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
    _populate_owner_choices(form)
    if request.method == "GET":
        form.owner_id.data = item.user_id or 0
    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.category_id = form.category_id.data
        item.type = form.type.data
        item.amount = form.amount.data
        item.frequency = form.frequency.data
        item.start_date = form.start_date.data
        item.user_id = form.owner_id.data or None
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
