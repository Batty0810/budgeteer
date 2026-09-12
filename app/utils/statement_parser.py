"""Best-effort extraction of transactions from a bank statement PDF.

Bank statement layouts vary enormously between (and even within) banks, so
this makes no claim to be exact - it's tuned to get the common case right
and leave everything else easy to fix by hand, which is why every row it
produces is a *reviewable suggestion*, never written straight to the ledger.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO

import pdfplumber

DATE_PATTERNS = [
    # 01/08/2026, 01-08-2026, 01.08.26
    re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})\b"),
    # 2026-08-01 (ISO)
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    # 01 Aug 2026 / 1 August 2026
    re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2,4})\b"),
]

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}

# An amount, optionally negative, optionally with a trailing Dr/Cr/D/C marker
# some SA bank statements append instead of a sign or a debit/credit column.
#
# The integer part is `\d{1,3}(?:,\d{3})+` (comma-grouped, e.g. 1,500) OR
# `\d+` (a bare run of digits, e.g. 15000) - never both as one `*`-repeated
# alternative, which would let the engine match just the last 3 digits of a
# longer bare number (e.g. matching "000.00" out of "15000.00"). The
# `(?<!\d)`/`(?!\d)` guards stop it from ever starting or ending mid-number.
AMOUNT_RE = re.compile(
    r"(-)?(?:R\s?)?(?<!\d)((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})(?!\d)\s?(Dr|Cr|DR|CR|D|C)?\b"
)

INCOME_KEYWORDS = [
    "salary", "deposit", "credit transfer", "refund", "interest", "payment received",
    "income", "reversal", "eft in", "cash deposit",
]

# Merchant/description keywords -> a category name to look for in the
# household's own categories. Only ever *suggests* an existing category -
# never invented, never created.
CATEGORY_HINTS = {
    "groceries": ["woolworths", "checkers", "pick n pay", "pnp ", "spar", "shoprite", "food lover"],
    "transport": ["uber", "bolt", "gautrain", "engen", "shell", "sasol", "bp garage", "fuel"],
    "entertainment": ["netflix", "showmax", "dstv", "spotify", "steam", "playstation"],
    "salary": ["salary", "payroll"],
    "utilities": ["eskom", "city power", "prepaid electricity", "municipality", "rates and taxes"],
    "medical": ["pharmacy", "clicks", "dischem", "medical aid", "discovery health"],
}

OPENING_BALANCE_RE = re.compile(r"(balance\s+brought\s+forward|opening\s+balance)", re.I)
CLOSING_BALANCE_RE = re.compile(r"(closing\s+balance|balance\s+carried\s+forward|new\s+balance)", re.I)


class StatementParseError(Exception):
    """Raised when the PDF can't be read at all (wrong password, corrupt file)."""


def _parse_date(day_str, month_str, year_str):
    day, month = int(day_str), None
    if month_str.isalpha():
        month = MONTHS.get(month_str.lower()[:3])
        if month is None:
            return None
    else:
        month = int(month_str)
        # Disambiguate day/month order: if the "month" is >12, they were swapped.
        if month > 12 and day <= 12:
            day, month = month, day
    year = int(year_str)
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_leading_date(line):
    for pattern in DATE_PATTERNS:
        m = pattern.match(line.strip())
        if not m:
            continue
        groups = m.groups()
        if pattern is DATE_PATTERNS[1]:  # ISO: year, month, day
            year_str, month_str, day_str = groups
        else:
            day_str, month_str, year_str = groups
        parsed = _parse_date(day_str, month_str, year_str)
        if parsed:
            return parsed, line[m.end():].strip()
    return None, None


def _guess_type(description, amounts_with_markers, default="expense"):
    for entry in amounts_with_markers:
        marker = entry[1]
        if marker and marker.lower() == "cr":
            return "income"
        if marker and marker.lower() == "dr":
            return "expense"
    lowered = description.lower()
    if any(kw in lowered for kw in INCOME_KEYWORDS):
        return "income"
    return default


def _guess_category_id(description, categories_by_name):
    lowered = description.lower()
    for cat_name, cat in categories_by_name.items():
        if cat_name in lowered:
            return cat.id
    for hint_name, keywords in CATEGORY_HINTS.items():
        if any(kw in lowered for kw in keywords):
            cat = categories_by_name.get(hint_name)
            if cat:
                return cat.id
    return None


def _clean_description(line, date_removed_line, amount_spans):
    text = date_removed_line
    # Strip the matched amount tokens (rightmost first so earlier spans stay valid).
    for start, end in sorted(amount_spans, reverse=True):
        text = text[:start] + text[end:]
    return re.sub(r"\s+", " ", text).strip(" -|\t")


def parse_pdf_statement(file_bytes, password=None, categories=None):
    """Extract transaction candidates from a PDF's bytes.

    Returns a dict: {"rows": [...], "opening_balance": Decimal|None,
    "closing_balance": Decimal|None, "statement_month": date|None}.
    Each row is {"date", "description", "amount", "type", "category_id",
    "raw_line"}. Raises StatementParseError if the PDF can't be opened.
    """
    categories = categories or []
    categories_by_name = {c.name.lower(): c for c in categories}

    try:
        doc = pdfplumber.open(BytesIO(file_bytes), password=password or "")
    except Exception as exc:  # pdfminer raises several distinct exception types
        raise StatementParseError(str(exc)) from exc

    rows = []
    opening_balance = None
    closing_balance = None
    all_dates = []

    with doc:
        for page in doc.pages:
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue

                if opening_balance is None and OPENING_BALANCE_RE.search(line):
                    amounts = AMOUNT_RE.findall(line)
                    if amounts:
                        opening_balance = _to_decimal(amounts[-1][1])
                    continue
                if CLOSING_BALANCE_RE.search(line):
                    amounts = AMOUNT_RE.findall(line)
                    if amounts:
                        closing_balance = _to_decimal(amounts[-1][1])
                    continue

                txn_date, rest = _extract_leading_date(line)
                if txn_date is None:
                    continue

                amount_matches = list(AMOUNT_RE.finditer(rest))
                if not amount_matches:
                    continue

                description = _clean_description(line, rest, [(m.start(), m.end()) for m in amount_matches])
                if len(description) < 2:
                    continue  # probably a stray balance/header line, not a transaction

                # (decimal value, Dr/Cr marker, whether this token had a leading '-'), in order found
                found = [
                    (_to_decimal(m.group(2)), m.group(3), bool(m.group(1)))
                    for m in amount_matches
                    if _to_decimal(m.group(2)) is not None
                ]
                if not found:
                    continue

                # Two-or-more amounts: assume "...amount, balance" (a genuinely
                # empty debit/credit column contributes no token at all, so the
                # common case is exactly these two). One amount: it *is* the
                # transaction amount, with no running balance on this line.
                if len(found) >= 2:
                    txn_amount, txn_marker, txn_negative = found[-2]
                    marker_context = found[-2:]
                else:
                    txn_amount, txn_marker, txn_negative = found[0]
                    marker_context = found

                if txn_negative:
                    txn_type = "expense"
                else:
                    txn_type = _guess_type(description, marker_context)

                all_dates.append(txn_date)
                rows.append(
                    {
                        "date": txn_date,
                        "description": description,
                        "amount": abs(txn_amount),
                        "type": txn_type,
                        "category_id": _guess_category_id(description, categories_by_name),
                        "raw_line": line[:500],
                    }
                )

    statement_month = None
    if all_dates:
        # Most common month among detected dates, not just the first row -
        # a handful of stray dates (e.g. a "since 2019" blurb) shouldn't skew it.
        month_counts = {}
        for d in all_dates:
            key = d.replace(day=1)
            month_counts[key] = month_counts.get(key, 0) + 1
        statement_month = max(month_counts, key=month_counts.get)

    return {
        "rows": rows,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "statement_month": statement_month,
    }


def _to_decimal(raw):
    try:
        return Decimal(raw.replace(",", "").replace(" ", ""))
    except (InvalidOperation, AttributeError):
        return None
