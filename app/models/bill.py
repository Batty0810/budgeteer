from datetime import date
from decimal import Decimal

from app.extensions import db

RECURRENCE_CHOICES = [
    (3, "Quarterly"),
    (6, "Twice a year"),
    (12, "Annual"),
]


class IrregularBill(db.Model):
    """A big, infrequent bill - annual insurance, quarterly rates, school fees.

    Budgeteer sets aside ``monthly_buffer`` (``amount / recurrence_months``)
    each month so the lump sum doesn't blindside the household when
    ``due_date`` arrives. ``saved_amount`` tracks progress toward it.
    """

    __tablename__ = "irregular_bills"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    recurrence_months = db.Column(db.Integer, nullable=False, default=12)
    saved_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    household = db.relationship("Household", back_populates="irregular_bills")
    category = db.relationship("Category", back_populates="irregular_bills")

    @property
    def monthly_buffer(self):
        if not self.recurrence_months:
            return Decimal("0")
        return (self.amount / self.recurrence_months).quantize(Decimal("0.01"))

    @property
    def months_remaining(self):
        today = date.today()
        months = (self.due_date.year - today.year) * 12 + (self.due_date.month - today.month)
        return max(months, 0)

    @property
    def progress_percent(self):
        if not self.amount:
            return 0
        pct = (self.saved_amount / self.amount) * 100
        return min(float(pct), 100.0)

    def __repr__(self):
        return f"<IrregularBill {self.name!r} due {self.due_date}>"
