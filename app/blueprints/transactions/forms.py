from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange, Length

from app.models.category import TYPE_INCOME, TYPE_EXPENSE
from app.models.recurring import FREQUENCY_CHOICES, FREQ_MONTHLY


class TransactionForm(FlaskForm):
    type = SelectField("Type", choices=[(TYPE_EXPENSE, "Expense"), (TYPE_INCOME, "Income")], validators=[DataRequired()])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    user_id = SelectField("Whose is this?", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount (R)", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    date = DateField("Date", validators=[DataRequired()])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    tags = StringField("Tags (comma separated)", validators=[Optional(), Length(max=255)])
    is_recurring = BooleanField("This repeats - add it to the forecast")
    frequency = SelectField("How often", choices=FREQUENCY_CHOICES, default=FREQ_MONTHLY)


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=80)])
    type = SelectField("Type", choices=[(TYPE_EXPENSE, "Expense"), (TYPE_INCOME, "Income")], validators=[DataRequired()])
    monthly_budget = DecimalField("Monthly budget (R, optional)", places=2, validators=[Optional(), NumberRange(min=0)])
    color = StringField("Colour", validators=[Optional(), Length(min=7, max=7)])


class OpeningBalanceForm(FlaskForm):
    # No NumberRange floor here - a real bank balance can be negative (overdraft) or zero.
    amount = DecimalField("Balance brought forward (R)", places=2, validators=[DataRequired()])
    note = StringField("Note", validators=[Optional(), Length(max=255)], render_kw={"placeholder": "e.g. per bank statement"})
