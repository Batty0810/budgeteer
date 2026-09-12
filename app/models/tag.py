from app.extensions import db


class Tag(db.Model):
    """A free-form label members can attach to transactions, e.g. 'holiday'."""

    __tablename__ = "tags"
    __table_args__ = (db.UniqueConstraint("household_id", "name", name="uq_tag_household_name"),)

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    name = db.Column(db.String(40), nullable=False)

    household = db.relationship("Household", back_populates="tags")

    def __repr__(self):
        return f"<Tag {self.name!r}>"
