from datetime import datetime, timezone

from app.extensions import db


class MonthlyOpeningBalance(db.Model):
    """A household-confirmed "balance brought forward" for a given month.

    By default, Budgeteer computes each month's opening balance by rolling
    the household's bank account balance forward/backward through the
    logged ledger. This lets a household override that computed figure with
    a known value (e.g. copied from an actual bank statement) when the two
    have drifted apart - every month from here on anchors to the override
    instead of the older computed chain.
    """

    __tablename__ = "monthly_opening_balances"
    __table_args__ = (db.UniqueConstraint("household_id", "month", name="uq_opening_balance_household_month"),)

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)

    # The first day of the budget period this balance applies to (the 1st of
    # the month, or e.g. the 25th for a household paid on the 25th).
    month = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    household = db.relationship("Household", back_populates="opening_balances")

    def __repr__(self):
        return f"<MonthlyOpeningBalance {self.month} R{self.amount}>"
