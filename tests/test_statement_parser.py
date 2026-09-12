from datetime import date
from decimal import Decimal

import pytest

from app.utils.statement_parser import parse_pdf_statement, StatementParseError
from tests.pdf_helpers import build_statement_pdf, SAMPLE_STATEMENT_LINES


def test_parses_dates_amounts_and_types_from_a_typical_layout():
    result = parse_pdf_statement(build_statement_pdf(SAMPLE_STATEMENT_LINES))

    assert result["opening_balance"] == Decimal("1500.00")
    assert result["closing_balance"] == Decimal("15777.65")
    assert result["statement_month"] == date(2026, 8, 1)

    rows = result["rows"]
    assert len(rows) == 5

    salary = rows[0]
    assert salary["date"] == date(2026, 8, 1)
    assert salary["description"] == "SALARY - ACME CORP"
    assert salary["amount"] == Decimal("15000.00")
    assert salary["type"] == "income"

    groceries = rows[1]
    assert groceries["amount"] == Decimal("450.25")
    assert groceries["type"] == "expense"

    interest = rows[4]
    assert interest["amount"] == Decimal("12.40")
    assert interest["type"] == "income"  # via the INCOME_KEYWORDS heuristic, not a Dr/Cr marker


def test_does_not_truncate_four_and_five_digit_amounts():
    """Regression check: the amount regex used to match only the last 3
    digits of a bare (non comma-grouped) number, e.g. "15000.00" -> "000.00"."""
    lines = ["01/08/2026 BIG DEPOSIT 123456.00 123456.00"]
    result = parse_pdf_statement(build_statement_pdf(lines))
    assert result["rows"][0]["amount"] == Decimal("123456.00")


def test_comma_grouped_amounts_also_parse_correctly():
    lines = ["01/08/2026 BIG DEPOSIT 12,345.67 12,345.67"]
    result = parse_pdf_statement(build_statement_pdf(lines))
    assert result["rows"][0]["amount"] == Decimal("12345.67")


def test_guesses_categories_from_household_categories_and_merchant_keywords():
    from collections import namedtuple

    Cat = namedtuple("Cat", ["id", "name"])
    categories = [Cat(1, "Groceries"), Cat(2, "Entertainment"), Cat(3, "Salary"), Cat(4, "Transport")]

    result = parse_pdf_statement(build_statement_pdf(SAMPLE_STATEMENT_LINES), categories=categories)
    by_description = {r["description"]: r["category_id"] for r in result["rows"]}

    assert by_description["SALARY - ACME CORP"] == 3
    assert by_description["WOOLWORTHS PNP SANDTON"] == 1
    assert by_description["DEBIT ORDER NETFLIX"] == 2
    assert by_description["UBER TRIP JOHANNESBURG"] == 4
    assert by_description["INTEREST RECEIVED"] is None  # no matching category exists - left for the user


def test_explicit_debit_credit_markers_override_keyword_guessing():
    lines = ["01/08/2026 SOMETHING UNUSUAL 500.00Cr 1000.00"]
    result = parse_pdf_statement(build_statement_pdf(lines))
    assert result["rows"][0]["type"] == "income"


def test_a_leading_minus_sign_always_means_expense():
    lines = ["01/08/2026 REFUND OF FEES -50.00 950.00"]
    result = parse_pdf_statement(build_statement_pdf(lines))
    assert result["rows"][0]["type"] == "expense"


def test_a_password_protected_pdf_parses_with_the_right_password():
    data = build_statement_pdf(SAMPLE_STATEMENT_LINES, password="secret123")
    result = parse_pdf_statement(data, password="secret123")
    assert len(result["rows"]) == 5


def test_a_password_protected_pdf_raises_a_clean_error_with_the_wrong_password():
    data = build_statement_pdf(SAMPLE_STATEMENT_LINES, password="secret123")
    with pytest.raises(StatementParseError):
        parse_pdf_statement(data, password="wrong-password")


def test_a_non_pdf_file_raises_a_clean_error_instead_of_crashing():
    with pytest.raises(StatementParseError):
        parse_pdf_statement(b"this is not a pdf")


def test_a_pdf_with_no_recognisable_transactions_returns_an_empty_list():
    lines = ["Thank you for banking with us.", "No transactions this period."]
    result = parse_pdf_statement(build_statement_pdf(lines))
    assert result["rows"] == []
