from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, URL


class WishlistItemForm(FlaskForm):
    name = StringField("Item", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    url = StringField("Link", validators=[Optional(), URL(), Length(max=500)])
    estimated_cost = DecimalField("Estimated cost (R)", places=2, validators=[DataRequired(), NumberRange(min=0.01)])


class ContributionForm(FlaskForm):
    amount = DecimalField("Amount (R)", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    note = StringField("Note", validators=[Optional(), Length(max=255)])
