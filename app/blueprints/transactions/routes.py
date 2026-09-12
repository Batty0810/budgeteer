from datetime import date

from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.category import Category
from app.models.opening_balance import MonthlyOpeningBalance
from app.models.tag import Tag
from app.models.transaction import Transaction
from app.utils.balances import get_month_running_balances
from app.utils.charts import next_category_color
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


@bp.route("/")
@login_required
def list_transactions():
    month_str = request.args.get("month")  # "YYYY-MM"
    if month_str:
        year, month = (int(p) for p in month_str.split("-"))
    else:
        today = date.today()
        year, month = today.year, today.month

    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    query = Transaction.query.filter(
        Transaction.household_id == current_user.household_id,
        Transaction.date >= start,
        Transaction.date < end,
    )

    category_id = request.args.get("category_id", type=int)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    tag_id = request.args.get("tag_id", type=int)
    if tag_id:
        query = query.filter(Transaction.tags.any(Tag.id == tag_id))

    transactions = query.order_by(Transaction.date.desc(), Transaction.created_at.desc()).all()
    total_income = sum((t.amount for t in transactions if t.type == "income"), start=0)
    total_expense = sum((t.amount for t in transactions if t.type == "expense"), start=0)

    opening_balance, running_balances, closing_balance = get_month_running_balances(
        current_user.household, start, end
    )
    has_override_this_month = (
        MonthlyOpeningBalance.query.filter_by(household_id=current_user.household_id, month=start).first()
        is not None
    )

    return render_template(
        "transactions/list.html",
        transactions=transactions,
        categories=_household_categories(),
        tags=Tag.query.filter_by(household_id=current_user.household_id).order_by(Tag.name).all(),
        month_str=f"{year:04d}-{month:02d}",
        total_income=total_income,
        total_expense=total_expense,
        selected_category_id=category_id,
        selected_tag_id=tag_id,
        opening_balance=opening_balance,
        running_balances=running_balances,
        closing_balance=closing_balance,
        has_override_this_month=has_override_this_month,
        is_filtered=bool(category_id or tag_id),
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
        db.session.commit()
        flash("Transaction logged.", "success")
        return redirect(url_for("transactions.list_transactions", month=txn.date.strftime("%Y-%m")))

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
        db.session.commit()
        flash("Transaction updated.", "success")
        return redirect(url_for("transactions.list_transactions", month=txn.date.strftime("%Y-%m")))

    return render_template("transactions/form.html", form=form, mode="edit", txn=txn)


@bp.route("/<int:txn_id>/delete", methods=["POST"])
@login_required
def delete_transaction(txn_id):
    txn = db.session.get(Transaction, txn_id)
    if txn is None or txn.household_id != current_user.household_id:
        abort(404)
    month_str = txn.date.strftime("%Y-%m")
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "info")
    return redirect(url_for("transactions.list_transactions", month=month_str))


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


@bp.route("/opening-balance", methods=["GET", "POST"])
@login_required
def set_opening_balance():
    month_str = request.args.get("month") or request.form.get("month")
    if month_str:
        year, month = (int(p) for p in month_str.split("-"))
    else:
        today = date.today()
        year, month = today.year, today.month
    month_start = date(year, month, 1)

    existing = MonthlyOpeningBalance.query.filter_by(
        household_id=current_user.household_id, month=month_start
    ).first()

    form = OpeningBalanceForm(obj=existing)
    if request.method == "GET" and existing is None:
        computed = get_month_running_balances(current_user.household, month_start, month_start + relativedelta(months=1))[0]
        form.amount.data = computed["amount"]

    if form.validate_on_submit():
        if existing is None:
            existing = MonthlyOpeningBalance(household_id=current_user.household_id, month=month_start)
            db.session.add(existing)
        existing.amount = form.amount.data
        existing.note = form.note.data
        db.session.commit()
        flash(f"Set the opening balance for {month_start.strftime('%B %Y')}.", "success")
        return redirect(url_for("transactions.list_transactions", month=month_start.strftime("%Y-%m")))

    return render_template(
        "transactions/opening_balance_form.html", form=form, month_start=month_start, existing=existing
    )


@bp.route("/opening-balance/clear", methods=["POST"])
@login_required
def clear_opening_balance():
    month_str = request.form.get("month")
    year, month = (int(p) for p in month_str.split("-"))
    month_start = date(year, month, 1)
    existing = MonthlyOpeningBalance.query.filter_by(
        household_id=current_user.household_id, month=month_start
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Cleared the manual opening balance for {month_start.strftime('%B %Y')}.", "info")
    return redirect(url_for("transactions.list_transactions", month=month_str))
