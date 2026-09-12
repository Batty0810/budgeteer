from datetime import datetime, timezone

from app.extensions import db

TYPE_INCOME = "income"
TYPE_EXPENSE = "expense"

# Validated categorical chart palette (dark-surface, colorblind-safe order).
# New categories are assigned the next colour in this fixed sequence so
# charts never repaint a category's colour when the category list is
# filtered - see app/utils/charts.py.
DEFAULT_CATEGORY_COLORS = [
    "#d94f4f",  # red
    "#8b7bff",  # purple
    "#b8790d",  # orange
    "#1a9fc4",  # cyan
    "#229954",  # green
    "#c23f8f",  # magenta
]


class Category(db.Model):
    """An income or expense bucket, e.g. 'Groceries' or 'Salary'.

    Categories are scoped to a household and can carry an optional monthly
    budget limit used by the dashboard's "remaining budget" widgets.
    """

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)

    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(10), nullable=False, default=TYPE_EXPENSE)
    color = db.Column(db.String(7), nullable=False, default="#8b7bff")
    icon = db.Column(db.String(40), nullable=True)
    monthly_budget = db.Column(db.Numeric(12, 2), nullable=True)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    household = db.relationship("Household", back_populates="categories")
    transactions = db.relationship("Transaction", back_populates="category")
    recurring_items = db.relationship("RecurringItem", back_populates="category")
    irregular_bills = db.relationship("IrregularBill", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name!r} ({self.type})>"
