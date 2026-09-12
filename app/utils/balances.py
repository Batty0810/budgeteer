"""Balance-brought-forward math for the transactions ledger.

Every month's opening balance is anchored to either a household-confirmed
override (`MonthlyOpeningBalance`) or, failing that, the household's bank
account balance (used elsewhere by the forecaster) - then rolled forward or
backward through the logged transactions between that anchor and the month
in question.
"""

from decimal import Decimal

from app.extensions import db
from app.models.account import BankAccount
from app.models.opening_balance import MonthlyOpeningBalance
from app.models.transaction import Transaction


def _signed_amount(txn_type, amount):
    return Decimal(amount) if txn_type == "income" else -Decimal(amount)


def _net_transactions_between(household_id, start_date, end_date):
    """Signed net of transactions with start_date <= date < end_date."""
    if start_date >= end_date:
        return Decimal("0")
    rows = (
        db.session.query(Transaction.type, Transaction.amount)
        .filter(
            Transaction.household_id == household_id,
            Transaction.date >= start_date,
            Transaction.date < end_date,
        )
        .all()
    )
    return sum((_signed_amount(t, a) for t, a in rows), Decimal("0"))


def get_balance_brought_forward(household, month_start):
    """The account balance at the instant before `month_start`'s transactions post.

    Returns a dict: {"amount": Decimal, "source": "override"|"account"|"none",
    "source_date": date or None} so the UI can explain where the figure came
    from.
    """
    household_id = household.id

    override = (
        MonthlyOpeningBalance.query.filter(
            MonthlyOpeningBalance.household_id == household_id,
            MonthlyOpeningBalance.month <= month_start,
        )
        .order_by(MonthlyOpeningBalance.month.desc())
        .first()
    )
    if override is not None:
        anchor_date, anchor_balance, source = override.month, Decimal(override.amount), "override"
    else:
        account = BankAccount.query.filter_by(household_id=household_id).first()
        if account is None:
            return {"amount": Decimal("0"), "source": "none", "source_date": None}
        anchor_date, anchor_balance, source = account.as_of_date, Decimal(account.starting_balance), "account"

    if anchor_date <= month_start:
        amount = anchor_balance + _net_transactions_between(household_id, anchor_date, month_start)
    else:
        amount = anchor_balance - _net_transactions_between(household_id, month_start, anchor_date)

    return {"amount": amount, "source": source, "source_date": anchor_date}


def get_month_running_balances(household, month_start, month_end):
    """Running balance after each transaction in [month_start, month_end).

    Computed in chronological order regardless of how the caller displays
    the list, and over *all* of the month's transactions regardless of any
    category/tag filter the UI applies - a running balance has to reflect
    every cash movement, not just the filtered subset on screen.

    Returns (opening_balance_info, {transaction_id: balance_after}, closing_balance).
    """
    opening = get_balance_brought_forward(household, month_start)
    txns = (
        Transaction.query.filter(
            Transaction.household_id == household.id,
            Transaction.date >= month_start,
            Transaction.date < month_end,
        )
        .order_by(Transaction.date.asc(), Transaction.created_at.asc(), Transaction.id.asc())
        .all()
    )

    running = opening["amount"]
    balances = {}
    for txn in txns:
        running += _signed_amount(txn.type, txn.amount)
        balances[txn.id] = running

    return opening, balances, running
