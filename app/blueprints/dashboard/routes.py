from datetime import date

from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models.category import Category, TYPE_EXPENSE, TYPE_INCOME
from app.models.transaction import Transaction
from app.models.bill import IrregularBill
from app.models.user import User
from app.models.wishlist import WishlistItem, STATUS_ARCHIVED

bp = Blueprint("dashboard", __name__, url_prefix="/")

MONTHS_OF_HISTORY = 6


def _month_bounds(year, month):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


@bp.route("/")
@login_required
def index():
    today = date.today()
    month_str = request.args.get("month", today.strftime("%Y-%m"))
    try:
        year, month = (int(p) for p in month_str.split("-"))
    except ValueError:
        year, month = today.year, today.month
    month_start, month_end = _month_bounds(year, month)

    household_id = current_user.household_id

    # --- Monthly cash flow (last N months, incl. selected month) ---
    # Aggregated in Python (rather than a SQL date-format function) so this
    # works unchanged on SQLite today and Postgres later.
    range_start = (month_start - relativedelta(months=MONTHS_OF_HISTORY - 1)).replace(day=1)
    rows = (
        db.session.query(Transaction.date, Transaction.type, Transaction.amount)
        .filter(
            Transaction.household_id == household_id,
            Transaction.date >= range_start,
            Transaction.date < month_end,
        )
        .all()
    )
    totals_by_month = {}
    labels = []
    cursor = range_start
    for _ in range(MONTHS_OF_HISTORY):
        ym = cursor.strftime("%Y-%m")
        labels.append(cursor.strftime("%b %Y"))
        totals_by_month[ym] = {"income": 0.0, "expense": 0.0}
        cursor += relativedelta(months=1)
    for txn_date, ttype, amount in rows:
        ym = txn_date.strftime("%Y-%m")
        if ym in totals_by_month:
            totals_by_month[ym][ttype] += float(amount)

    ordered = [totals_by_month[ym] for ym in sorted(totals_by_month)]
    cash_flow = {
        "labels": labels,
        "income": [m["income"] for m in ordered],
        "expense": [m["expense"] for m in ordered],
    }

    # --- Category breakdown for the selected month (expenses) ---
    breakdown_rows = (
        db.session.query(Category, func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.household_id == household_id,
            Transaction.type == TYPE_EXPENSE,
            Transaction.date >= month_start,
            Transaction.date < month_end,
        )
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    category_breakdown = [
        {"name": cat.name, "amount": float(total), "color": cat.color} for cat, total in breakdown_rows
    ]

    month_income = totals_by_month[f"{year:04d}-{month:02d}"]["income"]
    month_expense = totals_by_month[f"{year:04d}-{month:02d}"]["expense"]

    # --- Budget remaining per category ---
    budgeted_categories = (
        Category.query.filter(
            Category.household_id == household_id,
            Category.type == TYPE_EXPENSE,
            Category.is_archived == False,  # noqa: E712
            Category.monthly_budget.isnot(None),
        )
        .order_by(Category.name.asc())
        .all()
    )
    spent_lookup = {row["name"]: row["amount"] for row in category_breakdown}
    budgets = []
    for cat in budgeted_categories:
        spent = spent_lookup.get(cat.name, 0.0)
        budget = float(cat.monthly_budget)
        percent = (spent / budget * 100) if budget else 0
        if percent >= 100:
            status = "critical"
        elif percent >= 80:
            status = "warning"
        else:
            status = "good"
        budgets.append(
            {
                "name": cat.name,
                "color": cat.color,
                "spent": spent,
                "budget": budget,
                "remaining": budget - spent,
                "percent": min(percent, 100),
                "status": status,
            }
        )

    # --- By household member (who brings in / spends what, combined) ---
    member_rows = (
        db.session.query(Transaction.user_id, Transaction.type, func.sum(Transaction.amount))
        .filter(
            Transaction.household_id == household_id,
            Transaction.date >= month_start,
            Transaction.date < month_end,
        )
        .group_by(Transaction.user_id, Transaction.type)
        .all()
    )
    totals_by_user = {}
    for user_id, ttype, total in member_rows:
        totals_by_user.setdefault(user_id, {"income": 0.0, "expense": 0.0})[ttype] = float(total)

    household_users = User.query.filter_by(household_id=household_id).order_by(User.display_name.asc()).all()
    by_member = [
        {
            "name": u.display_name,
            "color": u.color,
            "income": totals_by_user.get(u.id, {}).get("income", 0.0),
            "expense": totals_by_user.get(u.id, {}).get("expense", 0.0),
        }
        for u in household_users
    ]

    # --- Irregular bill buffer summary ---
    active_bills = IrregularBill.query.filter_by(household_id=household_id, is_active=True).all()
    bill_summary = {
        "count": len(active_bills),
        "monthly_buffer_total": sum((b.monthly_buffer for b in active_bills), start=0),
        "saved_total": sum((b.saved_amount or 0 for b in active_bills), start=0),
    }

    # --- Wishlist teaser ---
    top_wishlist_items = (
        WishlistItem.query.filter(
            WishlistItem.household_id == household_id, WishlistItem.status != STATUS_ARCHIVED
        ).all()
    )
    top_wishlist_items.sort(key=lambda i: i.score, reverse=True)
    top_wishlist_items = top_wishlist_items[:3]

    prev_month_date = month_start - relativedelta(months=1)
    next_month_date = month_start + relativedelta(months=1)

    return render_template(
        "dashboard/index.html",
        month_label=month_start.strftime("%B %Y"),
        month_str=f"{year:04d}-{month:02d}",
        prev_month_str=prev_month_date.strftime("%Y-%m"),
        next_month_str=next_month_date.strftime("%Y-%m"),
        is_current_month=(year, month) == (today.year, today.month),
        month_income=month_income,
        month_expense=month_expense,
        net_cash_flow=month_income - month_expense,
        cash_flow=cash_flow,
        category_breakdown=category_breakdown,
        by_member=by_member,
        budgets=budgets,
        bill_summary=bill_summary,
        top_wishlist_items=top_wishlist_items,
    )
