from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField
from wtforms.validators import DataRequired, NumberRange, Length

from app.models.category import TYPE_INCOME, TYPE_EXPENSE
from app.models.recurring import FREQUENCY_CHOICES


class AccountForm(FlaskForm):
    name = StringField("Account name", validators=[DataRequired(), Length(max=80)])
    starting_balance = DecimalField("Current balance (R)", places=2, validators=[DataRequired()])
    as_of_date = DateField("As of", validators=[DataRequired()])


class RecurringItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    type = SelectField("Type", choices=[(TYPE_EXPENSE, "Expense"), (TYPE_INCOME, "Income")], validators=[DataRequired()])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    # 0 = shared by the household; otherwise a household member's user id.
    owner_id = SelectField("Whose is this?", coerce=int)
    amount = DecimalField("Amount (R)", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    frequency = SelectField("Frequency", choices=FREQUENCY_CHOICES, validators=[DataRequired()])
    start_date = DateField("Starts on", validators=[DataRequired()])
