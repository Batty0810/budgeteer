from decimal import Decimal


def format_zar(value):
    """Format a number as South African Rand, e.g. Decimal('1234.5') -> 'R 1,234.50'."""
    if value is None:
        value = 0
    value = Decimal(value)
    negative = value < 0
    value = abs(value)
    formatted = f"{value:,.2f}"
    sign = "-" if negative else ""
    return f"{sign}R {formatted}"


def register_filters(app):
    app.jinja_env.filters["zar"] = format_zar
