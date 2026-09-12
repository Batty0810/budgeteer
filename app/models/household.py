from datetime import datetime, timezone

from app.extensions import db


class Household(db.Model):
    """A shared budget unit - e.g. a couple or a house full of roommates.

    Every user, category, transaction and so on belongs to exactly one
    household. All members of a household see and manage the same data.
    """

    __tablename__ = "households"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users = db.relationship("User", back_populates="household", cascade="all, delete-orphan")
    categories = db.relationship("Category", back_populates="household", cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", back_populates="household", cascade="all, delete-orphan")
    tags = db.relationship("Tag", back_populates="household", cascade="all, delete-orphan")
    accounts = db.relationship("BankAccount", back_populates="household", cascade="all, delete-orphan")
    recurring_items = db.relationship("RecurringItem", back_populates="household", cascade="all, delete-orphan")
    irregular_bills = db.relationship("IrregularBill", back_populates="household", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="household", cascade="all, delete-orphan")
    opening_balances = db.relationship("MonthlyOpeningBalance", back_populates="household", cascade="all, delete-orphan")
    statement_imports = db.relationship("StatementImport", back_populates="household", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Household {self.name!r}>"
