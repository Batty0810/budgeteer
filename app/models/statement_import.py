from datetime import datetime, timezone

from app.extensions import db

STATUS_REVIEWING = "reviewing"
STATUS_COMPLETED = "completed"


class StatementImport(db.Model):
    """One PDF bank-statement upload, awaiting review before its rows
    become real transactions. Deleted (rows cascade) once the household
    confirms or cancels the import."""

    __tablename__ = "statement_imports"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Parser's best guesses, purely informational until/unless the user
    # applies them - see app/utils/statement_parser.py.
    opening_balance_guess = db.Column(db.Numeric(12, 2), nullable=True)
    closing_balance_guess = db.Column(db.Numeric(12, 2), nullable=True)
    statement_month_guess = db.Column(db.Date, nullable=True)

    household = db.relationship("Household", back_populates="statement_imports")
    uploaded_by = db.relationship("User")
    rows = db.relationship(
        "StatementImportRow", back_populates="statement_import", cascade="all, delete-orphan", order_by="StatementImportRow.date"
    )

    def __repr__(self):
        return f"<StatementImport {self.filename!r} ({len(self.rows)} rows)>"


class StatementImportRow(db.Model):
    """One transaction candidate extracted from a statement, editable on
    the review page before it's turned into a real Transaction."""

    __tablename__ = "statement_import_rows"

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey("statement_imports.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    type = db.Column(db.String(10), nullable=False, default="expense")
    raw_line = db.Column(db.String(500), nullable=True)

    include = db.Column(db.Boolean, nullable=False, default=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    recurring_frequency = db.Column(db.String(20), nullable=True)

    statement_import = db.relationship("StatementImport", back_populates="rows")
    category = db.relationship("Category")

    def __repr__(self):
        return f"<StatementImportRow {self.date} {self.description!r} {self.amount}>"
