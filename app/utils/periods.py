"""Budget periods - the date ranges the dashboard and ledger report on.

A household's "budget month" starts on a configurable day (e.g. the 25th,
when the salary lands) instead of always on the 1st, so income and the
expenses it pays for fall in the same period. Any page can also be shown
for an explicit custom range (?start=YYYY-MM-DD&end=YYYY-MM-DD).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from flask import request, url_for

# Capped at 28 so every month has the start day.
MAX_START_DAY = 28

# Average month length, for scaling monthly budgets to custom ranges.
AVG_MONTH_DAYS = 365.25 / 12


def format_date_range(start, end):
    if start == end:
        return start.strftime("%d %b %Y")
    if start.year == end.year:
        return f"{start:%d %b} – {end:%d %b %Y}"
    return f"{start:%d %b %Y} – {end:%d %b %Y}"


@dataclass(frozen=True)
class Period:
    start: date  # first day, inclusive
    end: date  # last day, inclusive
    start_day: int = 1  # the household's budget-month start day

    @property
    def end_exclusive(self):
        """For queries: start <= date < end_exclusive."""
        return self.end + timedelta(days=1)

    @property
    def days(self):
        return (self.end - self.start).days + 1

    @property
    def cycle_count(self):
        """How many whole budget periods this spans, or None for a custom range
        that doesn't line up with the household's cycle."""
        if self.start.day != self.start_day:
            return None
        cursor, count = self.start, 0
        while cursor <= self.end:
            cursor += relativedelta(months=1)
            count += 1
            if cursor - timedelta(days=1) == self.end:
                return count
        return None

    @property
    def is_cycle(self):
        return self.cycle_count == 1

    @property
    def budget_factor(self):
        """Multiplier that turns a monthly budget into a budget for this period."""
        return self.cycle_count or self.days / AVG_MONTH_DAYS

    @property
    def label(self):
        if self.is_cycle and self.start_day == 1:
            return self.start.strftime("%B %Y")
        return format_date_range(self.start, self.end)

    @property
    def short_label(self):
        """Compact label for chart axes."""
        if self.start_day == 1:
            return self.start.strftime("%b %Y")
        return f"{self.start:%d %b}–{self.end:%d %b}"

    def contains(self, day):
        return self.start <= day <= self.end

    def shifted(self, n):
        """The period n steps later (or earlier, if negative) - one budget
        period per step, or the range's own length for a custom range."""
        if self.cycle_count:
            start = self.start + relativedelta(months=n * self.cycle_count)
            return Period(start, start + relativedelta(months=self.cycle_count) - timedelta(days=1), self.start_day)
        offset = timedelta(days=n * self.days)
        return Period(self.start + offset, self.end + offset, self.start_day)

    def query_args(self):
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def period_containing(day, start_day=1):
    """The budget period (start_day to the day before start_day next month)
    that `day` falls in."""
    start = day if day.day >= start_day else day - relativedelta(months=1)
    start = start.replace(day=start_day)
    return Period(start, start + relativedelta(months=1) - timedelta(days=1), start_day)


def recent_cycles(period, count):
    """The `count` budget periods ending with the one containing period.end,
    oldest first - for month-by-month charts."""
    last = period_containing(period.end, period.start_day)
    return [last.shifted(-i) for i in range(count - 1, -1, -1)]


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def resolve_period(args, start_day=1, today=None):
    """Work out the period a page should show from its query string.

    ?start=&end= gives a custom range (end inclusive); ?month=YYYY-MM is the
    budget period that starts in that month (kept for older links);
    otherwise it's the period containing today.
    """
    today = today or date.today()
    start, end = _parse_date(args.get("start")), _parse_date(args.get("end"))
    if start and end:
        if end < start:
            start, end = end, start
        return Period(start, end, start_day)
    if start or end:
        return period_containing(start or end, start_day)

    month = args.get("month")
    if month:
        try:
            year, month_num = (int(p) for p in month.split("-"))
            return period_containing(date(year, month_num, start_day), start_day)
        except ValueError:
            pass

    return period_containing(today, start_day)


def period_nav(period, today=None):
    """URLs for the period picker on the current page: previous/next period
    and back to the current one, keeping any other filters in the query
    string. `hidden` is those other filters, for the picker's own form."""
    today = today or date.today()
    other_args = {k: v for k, v in request.args.items() if k not in ("start", "end", "month")}

    def url(p):
        return url_for(request.endpoint, **other_args, **p.query_args())

    current = period_containing(today, period.start_day)
    return {
        "prev_url": url(period.shifted(-1)),
        "next_url": url(period.shifted(1)),
        "current_url": url_for(request.endpoint, **other_args),
        "is_current": period == current,
        "hidden": other_args,
    }
