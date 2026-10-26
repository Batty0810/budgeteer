from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.category import Category
from app.models.opening_balance import MonthlyOpeningBalance
from app.models.recurring import RecurringItem
from app.models.tag import Tag
from app.models.transaction import Transaction
from app.models.user import User
from app.utils.balances import get_month_running_balances
from app.utils.charts import next_category_color
from app.utils.forecasting import frequency_step
from app.utils.periods import Period, period_containing, period_nav, resolve_period
from app.blueprints.transactions.forms import TransactionForm, CategoryForm, OpeningBalanceForm

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


def _household_categories(include_archived=False):
    query = Category.query.filter_by(household_id=current_user.household_id)
    if not include_archived:
        query = query.filter_by(is_archived=False)
    return query.order_by(Category.type.asc(), Category.name.asc()).all()


def _populate_category_choices(form, include_category=None):
    categories = _household_categories()
    # A transaction's category may have been archived since it was logged -
    # keep it selectable when editing so the form doesn't reject a value it
    # rendered itself.
    if include_category and include_category.is_archived and include_category not in categories:
        categories = categories + [include_category]
    form.category_id.choices = [
        (c.id, f"{c.name} ({'Income' if c.type == 'income' else 'Expense'})" + (" - archived" if c.is_archived else ""))
        for c in categories
    ]


def _sync_tags(raw_tags):
    names = {t.strip() for t in raw_tags.split(",") if t.strip()} if raw_tags else set()
    tags = []
    for name in names:
        tag = Tag.query.filter_by(household_id=current_user.household_id, name=name).first()
        if tag is None:
            tag = Tag(household_id=current_user.household_id, name=name)
            db.session.add(tag)
            db.session.flush()
        tags.append(tag)
    return tags


def _make_recurring(txn, frequency):
    """Set up a recurring item for the forecaster from a logged transaction.

    The transaction itself is the first occurrence, so the recurring item
    starts at the next one - otherwise a future-dated transaction would be
    counted twice in the forecast.
    """
    item = RecurringItem(
        household_id=txn.household_id,
        category_id=txn.category_id,
        user_id=txn.user_id,
        name=(txn.description or txn.category.name)[:120],
        type=txn.type,
        amount=txn.amount,
        frequency=frequency,
        start_date=txn.date + frequency_step(frequency),
    )
    db.session.add(item)
    txn.recurring_item = item
    return item


def _ledger_url_for(day):
    """The transactions list for the budget period containing `day`."""
    period = period_containing(day, current_user.household.period_start_day)
    return url_for("transactions.list_transactions", **period.query_args())


@bp.route("/")
@login_required
def list_transactions():
    period = resolve_period(request.args, current_user.household.period_start_day)
    start, end = period.start, period.end_exclusive

    query = Transaction.query.filter(
        Transaction.household_id == current_user.household_id,
        Transaction.date >= start,
        Transaction.date < end,
    )

    txn_type = request.args.get("type")
    if txn_type not in ("income", "expense"):
        txn_type = None
    if txn_type:
        query = query.filter(Transaction.type == txn_type)

    category_id = request.args.get("category_id", type=int)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    tag_id = request.args.get("tag_id", type=int)
    if tag_id:
        query = query.filter(Transaction.tags.any(Tag.id == tag_id))

    user_id = request.args.get("user_id", type=int)
    if user_id:
        query = query.filter(Transaction.user_id == user_id)

    # Oldest first, like a bank statement, so the Balance column reads
    # top-to-bottom from brought forward to closing.
    transactions = query.order_by(Transaction.date.asc(), Transaction.created_at.asc(), Transaction.id.asc()).all()
    total_income = sum((t.amount for t in transactions if t.type == "income"), start=0)
    total_expense = sum((t.amount for t in transactions if t.type == "expense"), start=0)

    opening_balance, running_balances, closing_balance = get_month_running_balances(
        current_user.household, start, end
    )
    has_override_this_period = (
        MonthlyOpeningBalance.query.filter_by(household_id=current_user.household_id, month=start).first()
        is not None
    )

    return render_template(
        "transactions/list.html",
        transactions=transactions,
        categories=_household_categories(),
        tags=Tag.query.filter_by(household_id=current_user.household_id).order_by(Tag.name).all(),
        household_users=User.query.filter_by(household_id=current_user.household_id).order_by(User.display_name).all(),
        period=period,
        nav=period_nav(period),
        total_income=total_income,
        total_expense=total_expense,
        selected_type=txn_type,
        selected_category_id=category_id,
        selected_tag_id=tag_id,
        selected_user_id=user_id,
        opening_balance=opening_balance,
        running_balances=running_balances,
        closing_balance=closing_balance,
        has_override_this_period=has_override_this_period,
        is_filtered=bool(txn_type or category_id or tag_id or user_id),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_transaction():
    form = TransactionForm()
    _populate_category_choices(form)
    if request.method == "GET":
        form.date.data = date.today()

    if form.validate_on_submit():
        txn = Transaction(
            household_id=current_user.household_id,
            user_id=current_user.id,
            category_id=form.category_id.data,
            type=form.type.data,
            amount=form.amount.data,
            description=form.description.data,
            date=form.date.data,
        )
        txn.tags = _sync_tags(form.tags.data)
        db.session.add(txn)
        if form.is_recurring.data:
            db.session.flush()  # load txn.category for the recurring item's name
            _make_recurring(txn, form.frequency.data)
        db.session.commit()
        flash("Transaction logged" + (" and added to the forecast as recurring." if form.is_recurring.data else "."), "success")
        return redirect(_ledger_url_for(txn.date))

    return render_template("transactions/form.html", form=form, mode="new")


@bp.route("/<int:txn_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(txn_id):
    txn = db.session.get(Transaction, txn_id)
    if txn is None or txn.household_id != current_user.household_id:
        abort(404)

    form = TransactionForm(obj=txn)
    _populate_category_choices(form, include_category=txn.category)
    if request.method == "GET":
        form.tags.data = ", ".join(t.name for t in txn.tags)

    if form.validate_on_submit():
        txn.category_id = form.category_id.data
        txn.type = form.type.data
        txn.amount = form.amount.data
        txn.description = form.description.data
        txn.date = form.date.data
        txn.tags = _sync_tags(form.tags.data)
        made_recurring = form.is_recurring.data and txn.recurring_item is None
        if made_recurring:
            db.session.flush()
            _make_recurring(txn, form.frequency.data)
        db.session.commit()
        flash("Transaction updated" + (" and added to the forecast as recurring." if made_recurring else "."), "success")
        return redirect(_ledger_url_for(txn.date))

    return render_template("transactions/form.html", form=form, mode="edit", txn=txn)


@bp.route("/<int:txn_id>/delete", methods=["POST"])
@login_required
def delete_transaction(txn_id):
    txn = db.session.get(Transaction, txn_id)
    if txn is None or txn.household_id != current_user.household_id:
        abort(404)
    txn_date = txn.date
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "info")
    return redirect(_ledger_url_for(txn_date))


@bp.route("/categories")
@login_required
def list_categories():
    return render_template("transactions/categories.html", categories=_household_categories(include_archived=True))


@bp.route("/categories/new", methods=["GET", "POST"])
@login_required
def new_category():
    form = CategoryForm()
    if request.method == "GET":
        form.color.data = next_category_color(
            Category.query.filter_by(household_id=current_user.household_id).count()
        )
    if form.validate_on_submit():
        color = form.color.data or next_category_color(
            Category.query.filter_by(household_id=current_user.household_id).count()
        )
        category = Category(
            household_id=current_user.household_id,
            name=form.name.data.strip(),
            type=form.type.data,
            monthly_budget=form.monthly_budget.data,
            color=color,
        )
        db.session.add(category)
        db.session.commit()
        flash(f"Added category {category.name!r}.", "success")
        return redirect(url_for("transactions.list_categories"))
    return render_template("transactions/category_form.html", form=form, mode="new")


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None or category.household_id != current_user.household_id:
        abort(404)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        category.name = form.name.data.strip()
        category.type = form.type.data
        category.monthly_budget = form.monthly_budget.data
        category.color = form.color.data or category.color
        db.session.commit()
        flash(f"Updated category {category.name!r}.", "success")
        return redirect(url_for("transactions.list_categories"))
    return render_template("transactions/category_form.html", form=form, mode="edit", category=category)


@bp.route("/categories/<int:category_id>/archive-toggle", methods=["POST"])
@login_required
def toggle_category_archive(category_id):
    category = db.session.get(Category, category_id)
    if category is None or category.household_id != current_user.household_id:
        abort(404)
    category.is_archived = not category.is_archived
    db.session.commit()
    return redirect(url_for("transactions.list_categories"))


def _opening_balance_period(values):
    """The period whose balance brought forward is being set, from
    start/end (YYYY-MM-DD) or, for older links, month (YYYY-MM)."""
    start_day = current_user.household.period_start_day
    try:
        start = date.fromisoformat(values["start"])
    except (KeyError, ValueError):
        return resolve_period({"month": values.get("month")}, start_day)
    try:
        return Period(start, date.fromisoformat(values["end"]), start_day)
    except (KeyError, ValueError):
        return period_containing(start, start_day)


@bp.route("/opening-balance", methods=["GET", "POST"])
@login_required
def set_opening_balance():
    period = _opening_balance_period(request.values)

    existing = MonthlyOpeningBalance.query.filter_by(
        household_id=current_user.household_id, month=period.start
    ).first()

    form = OpeningBalanceForm(obj=existing)
    if request.method == "GET" and existing is None:
        computed = get_month_running_balances(current_user.household, period.start, period.end_exclusive)[0]
        form.amount.data = computed["amount"]

    if form.validate_on_submit():
        if existing is None:
            existing = MonthlyOpeningBalance(household_id=current_user.household_id, month=period.start)
            db.session.add(existing)
        existing.amount = form.amount.data
        existing.note = form.note.data
        db.session.commit()
        flash(f"Set the balance brought forward for {period.start:%d %B %Y}.", "success")
        return redirect(url_for("transactions.list_transactions", **period.query_args()))

    return render_template(
        "transactions/opening_balance_form.html", form=form, period=period, existing=existing
    )


@bp.route("/opening-balance/clear", methods=["POST"])
@login_required
def clear_opening_balance():
    period = _opening_balance_period(request.form)
    existing = MonthlyOpeningBalance.query.filter_by(
        household_id=current_user.household_id, month=period.start
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Cleared the manual balance brought forward for {period.start:%d %B %Y}.", "info")
    return redirect(url_for("transactions.list_transactions", **period.query_args()))
