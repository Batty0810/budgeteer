from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models.category import Category, TYPE_EXPENSE, TYPE_INCOME
from app.models.transaction import Transaction
from app.models.bill import IrregularBill
from app.models.user import User
from app.models.wishlist import WishlistItem, STATUS_ARCHIVED
from app.utils.periods import resolve_period, recent_cycles, period_nav

bp = Blueprint("dashboard", __name__, url_prefix="/")

PERIODS_OF_HISTORY = 6


@bp.route("/")
@login_required
def index():
    household_id = current_user.household_id
    period = resolve_period(request.args, current_user.household.period_start_day)
    period_start, period_end = period.start, period.end_exclusive

    # --- Cash flow per budget period (last N, ending with the selected one) ---
    # Aggregated in Python (rather than a SQL date-format function) so this
    # works unchanged on SQLite and Postgres.
    cycles = recent_cycles(period, PERIODS_OF_HISTORY)
    rows = (
        db.session.query(Transaction.date, Transaction.type, Transaction.amount)
        .filter(
            Transaction.household_id == household_id,
            Transaction.date >= min(cycles[0].start, period_start),
            Transaction.date < max(cycles[-1].end_exclusive, period_end),
        )
        .all()
    )
    cycle_totals = [{"income": 0.0, "expense": 0.0} for _ in cycles]
    month_income = month_expense = 0.0
    for txn_date, ttype, amount in rows:
        for cycle, totals in zip(cycles, cycle_totals):
            if cycle.contains(txn_date):
                totals[ttype] += float(amount)
                break
        if period.contains(txn_date):
            if ttype == TYPE_INCOME:
                month_income += float(amount)
            else:
                month_expense += float(amount)

    cash_flow = {
        "labels": [c.short_label for c in cycles],
        "income": [t["income"] for t in cycle_totals],
        "expense": [t["expense"] for t in cycle_totals],
    }

    # --- Category breakdown for the selected month (expenses) ---
    breakdown_rows = (
        db.session.query(Category, func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.household_id == household_id,
            Transaction.type == TYPE_EXPENSE,
            Transaction.date >= period_start,
            Transaction.date < period_end,
        )
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    category_breakdown = [
        {"name": cat.name, "amount": float(total), "color": cat.color} for cat, total in breakdown_rows
    ]

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
        budget = float(cat.monthly_budget) * period.budget_factor
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
            Transaction.date >= period_start,
            Transaction.date < period_end,
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

    return render_template(
        "dashboard/index.html",
        period=period,
        nav=period_nav(period),
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
