from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"


class User(db.Model, UserMixin):
    """A person who can log in to Budgeteer.

    Admins can create/manage other user accounts (via the admin blueprint)
    in addition to using the app like everyone else. There is no public
    self-registration - accounts are provisioned by an admin.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_MEMBER)
    color = db.Column(db.String(7), nullable=False, default="#6c63ff")

    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    household = db.relationship("Household", back_populates="users")
    transactions = db.relationship("Transaction", back_populates="logged_by", foreign_keys="Transaction.user_id")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_active(self):
        # Overrides UserMixin.is_active so deactivated accounts can't log in.
        return self.is_active_flag

    @property
    def initials(self):
        parts = self.display_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.display_name[:2].upper()

    def __repr__(self):
        return f"<User {self.email!r}>"
