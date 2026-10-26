"""Day-by-day cash flow projection.

Combines a household's bank account starting balance with its recurring
income/expenses, irregular (lump-sum) bills, and any future one-off
transactions already logged, to project the balance forward day by day.
"""

from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.models.recurring import (
    FREQ_WEEKLY,
    FREQ_BIWEEKLY,
    FREQ_MONTHLY,
    FREQ_QUARTERLY,
    FREQ_ANNUAL,
)


def frequency_step(frequency):
    """The gap between occurrences of a recurring item."""
    return {
        FREQ_WEEKLY: relativedelta(weeks=1),
        FREQ_BIWEEKLY: relativedelta(weeks=2),
        FREQ_MONTHLY: relativedelta(months=1),
        FREQ_QUARTERLY: relativedelta(months=3),
        FREQ_ANNUAL: relativedelta(years=1),
    }.get(frequency, relativedelta(months=1))


def _recurring_occurrences(item, range_start, range_end):
    """Yield each date `item` fires on within [range_start, range_end]."""
    step = frequency_step(item.frequency)

    cursor = item.start_date
    # Fast-forward to the first occurrence on/after range_start without
    # looping one step at a time over long histories.
    if cursor < range_start:
        # Binary-ish jump: estimate whole steps then fine-tune.
        while cursor < range_start:
            next_cursor = cursor + step
            if next_cursor == cursor:  # safety net against a zero-length step
                break
            cursor = next_cursor

    while cursor <= range_end:
        if item.end_date and cursor > item.end_date:
            break
        if cursor >= range_start:
            yield cursor
        cursor = cursor + step


def _bill_occurrences(bill, range_start, range_end):
    """Yield each due date for an irregular bill within the window."""
    cursor = bill.due_date
    step = relativedelta(months=bill.recurrence_months or 12)
    while cursor < range_start:
        cursor = cursor + step
    while cursor <= range_end:
        yield cursor
        cursor = cursor + step


def project_cash_flow(household, months=3, starting_balance=None, starting_date=None, recurring_items=None, bills=None, future_transactions=None):
    """Return a list of {date, balance, events} dicts spanning `months` months.

    `recurring_items`, `bills`, and `future_transactions` may be pre-fetched
    (already filtered to active/household-scoped) to avoid extra queries;
    otherwise they're pulled from the household's relationships.
    """
    today = starting_date or date.today()
    horizon = today + relativedelta(months=months)
    balance = Decimal(starting_balance if starting_balance is not None else 0)

    recurring_items = recurring_items if recurring_items is not None else [r for r in household.recurring_items if r.is_active]
    bills = bills if bills is not None else [b for b in household.irregular_bills if b.is_active]
    future_transactions = future_transactions if future_transactions is not None else []

    # Pre-compute every event across the whole window. Each is a dict:
    # {"amount": signed Decimal, "label": str, "type": "income"|"expense",
    #  "who": display name, or None for household-shared items}.
    events_by_date = {}

    def add_event(d, ttype, amount, label, who):
        signed = Decimal(amount) if ttype == "income" else -Decimal(amount)
        events_by_date.setdefault(d, []).append({"amount": signed, "label": label, "type": ttype, "who": who})

    for item in recurring_items:
        who = item.owner.display_name if item.owner else None
        for occ in _recurring_occurrences(item, today, horizon):
            add_event(occ, item.type, item.amount, item.name, who)

    for bill in bills:
        for occ in _bill_occurrences(bill, today, horizon):
            add_event(occ, "expense", bill.amount, bill.name, None)

    for txn in future_transactions:
        if today <= txn.date <= horizon:
            add_event(txn.date, txn.type, txn.amount, txn.description or txn.category.name, txn.logged_by.display_name)

    timeline = []
    cursor = today
    while cursor <= horizon:
        day_events = events_by_date.get(cursor, [])
        day_net = sum((e["amount"] for e in day_events), Decimal("0"))
        balance += day_net
        timeline.append(
            {
                "date": cursor,
                "balance": balance,
                "net": day_net,
                "events": day_events,
            }
        )
        cursor += timedelta(days=1)

    return timeline
