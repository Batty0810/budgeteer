from datetime import datetime, date, timezone

from app.extensions import db
from app.models.category import TYPE_EXPENSE

transaction_tags = db.Table(
    "transaction_tags",
    db.Column("transaction_id", db.Integer, db.ForeignKey("transactions.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Transaction(db.Model):
    """A single logged income or expense entry.

    Month-on-month history is simply every Transaction row ever created,
    scoped by household and grouped by ``date`` when the dashboard needs a
    monthly view - nothing is ever rolled up and discarded.
    """

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    recurring_item_id = db.Column(db.Integer, db.ForeignKey("recurring_items.id"), nullable=True)

    type = db.Column(db.String(10), nullable=False, default=TYPE_EXPENSE)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    household = db.relationship("Household", back_populates="transactions")
    logged_by = db.relationship("User", back_populates="transactions", foreign_keys=[user_id])
    category = db.relationship("Category", back_populates="transactions")
    recurring_item = db.relationship("RecurringItem", back_populates="generated_transactions")
    tags = db.relationship("Tag", secondary=transaction_tags, backref="transactions")

    def __repr__(self):
        return f"<Transaction {self.type} {self.amount} {self.date}>"
