from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField
from wtforms.validators import DataRequired, NumberRange, Length

from app.models.bill import RECURRENCE_CHOICES


class IrregularBillForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Total amount due (R)", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    due_date = DateField("Next due date", validators=[DataRequired()])
    recurrence_months = SelectField("Repeats every", choices=RECURRENCE_CHOICES, coerce=int, validators=[DataRequired()])
