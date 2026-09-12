"""Helpers for building tiny synthetic bank-statement-like PDFs in tests.

Real bank statements are far messier than this, but the parser is a
best-effort text-pattern matcher (see app/utils/statement_parser.py) rather
than a per-bank template engine, so a plain "date description amount
balance" layout is a faithful enough stand-in for testing its logic.
"""

from fpdf import FPDF


def build_statement_pdf(lines, password=None):
    pdf = FPDF()
    if password:
        pdf.set_encryption(owner_password=password + "-owner", user_password=password)
    pdf.add_page()
    pdf.set_font("Courier", size=10)
    for line in lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


SAMPLE_STATEMENT_LINES = [
    "Statement Period: 01 Aug 2026 to 31 Aug 2026",
    "Balance Brought Forward                                          1500.00",
    "01/08/2026 SALARY - ACME CORP                    15000.00          16500.00",
    "03/08/2026 WOOLWORTHS PNP SANDTON                              450.25   16049.75",
    "05/08/2026 DEBIT ORDER NETFLIX                                  199.00   15850.75",
    "07/08/2026 UBER TRIP JOHANNESBURG                                85.50   15765.25",
    "10/08/2026 INTEREST RECEIVED                        12.40           15777.65",
    "Closing Balance                                                  15777.65",
]
