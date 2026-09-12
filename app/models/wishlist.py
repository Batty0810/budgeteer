from datetime import datetime, date, timezone
from decimal import Decimal

from app.extensions import db

STATUS_PROPOSED = "proposed"
STATUS_SAVING = "saving"
STATUS_PURCHASED = "purchased"
STATUS_ARCHIVED = "archived"

STATUS_LABELS = {
    STATUS_PROPOSED: "Proposed",
    STATUS_SAVING: "Saving up",
    STATUS_PURCHASED: "Purchased",
    STATUS_ARCHIVED: "Archived",
}


class WishlistItem(db.Model):
    """A non-essential purchase the household is considering together."""

    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=True)
    estimated_cost = db.Column(db.Numeric(12, 2), nullable=False)
    saved_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PROPOSED)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    household = db.relationship("Household", back_populates="wishlist_items")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    votes = db.relationship("WishlistVote", back_populates="item", cascade="all, delete-orphan")
    contributions = db.relationship(
        "WishlistContribution", back_populates="item", cascade="all, delete-orphan", order_by="desc(WishlistContribution.date)"
    )

    @property
    def score(self):
        return sum(v.value for v in self.votes)

    @property
    def progress_percent(self):
        if not self.estimated_cost:
            return 0
        pct = (self.saved_amount / self.estimated_cost) * 100
        return min(float(pct), 100.0)

    @property
    def remaining_cost(self):
        remaining = self.estimated_cost - self.saved_amount
        return remaining if remaining > 0 else Decimal("0")

    def __repr__(self):
        return f"<WishlistItem {self.name!r}>"


class WishlistVote(db.Model):
    """One household member's vote (up/down) on a wishlist item."""

    __tablename__ = "wishlist_votes"
    __table_args__ = (db.UniqueConstraint("wishlist_item_id", "user_id", name="uq_vote_item_user"),)

    id = db.Column(db.Integer, primary_key=True)
    wishlist_item_id = db.Column(db.Integer, db.ForeignKey("wishlist_items.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False, default=1)  # 1 = up, -1 = down

    item = db.relationship("WishlistItem", back_populates="votes")
    user = db.relationship("User")


class WishlistContribution(db.Model):
    """A deposit a household member made toward a shared wishlist item."""

    __tablename__ = "wishlist_contributions"

    id = db.Column(db.Integer, primary_key=True)
    wishlist_item_id = db.Column(db.Integer, db.ForeignKey("wishlist_items.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), nullable=True)

    item = db.relationship("WishlistItem", back_populates="contributions")
    user = db.relationship("User")
