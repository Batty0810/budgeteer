from datetime import date

from app.extensions import db


class BankAccount(db.Model):
    """A real-world bank account whose balance the forecaster projects forward."""

    __tablename__ = "bank_accounts"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)

    name = db.Column(db.String(80), nullable=False, default="Main Account")
    starting_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    as_of_date = db.Column(db.Date, nullable=False, default=date.today)

    household = db.relationship("Household", back_populates="accounts")

    def __repr__(self):
        return f"<BankAccount {self.name!r} R{self.starting_balance}>"
