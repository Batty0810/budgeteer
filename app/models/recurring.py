from datetime import date

from app.extensions import db
from app.models.category import TYPE_EXPENSE

FREQ_WEEKLY = "weekly"
FREQ_BIWEEKLY = "biweekly"
FREQ_MONTHLY = "monthly"
FREQ_QUARTERLY = "quarterly"
FREQ_ANNUAL = "annual"

FREQUENCY_CHOICES = [
    (FREQ_WEEKLY, "Weekly"),
    (FREQ_BIWEEKLY, "Every 2 weeks"),
    (FREQ_MONTHLY, "Monthly"),
    (FREQ_QUARTERLY, "Quarterly"),
    (FREQ_ANNUAL, "Annual"),
]


class RecurringItem(db.Model):
    """A recurring income or expense - salary, rent, a subscription, etc.

    Used to auto-populate expected transactions and drives the cash flow
    forecaster's day-by-day projection.
    """

    __tablename__ = "recurring_items"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    # Whose income/expense this is, for the forecaster's per-person view.
    # None means it's shared by the household (rent, utilities, ...).
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(10), nullable=False, default=TYPE_EXPENSE)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    frequency = db.Column(db.String(20), nullable=False, default=FREQ_MONTHLY)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    household = db.relationship("Household", back_populates="recurring_items")
    category = db.relationship("Category", back_populates="recurring_items")
    owner = db.relationship("User")
    generated_transactions = db.relationship("Transaction", back_populates="recurring_item")

    def __repr__(self):
        return f"<RecurringItem {self.name!r} {self.frequency}>"
