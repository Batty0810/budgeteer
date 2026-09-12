from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional

from app.models.user import ROLE_ADMIN, ROLE_MEMBER

ROLE_CHOICES = [(ROLE_MEMBER, "Member"), (ROLE_ADMIN, "Admin")]


class NewUserForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Temporary password", validators=[DataRequired(), Length(min=8)])
    role = SelectField("Role", choices=ROLE_CHOICES, default=ROLE_MEMBER)
    color = StringField("Colour", validators=[Optional(), Length(min=7, max=7)], default="#6c63ff")


class EditUserForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField("Role", choices=ROLE_CHOICES, default=ROLE_MEMBER)
    color = StringField("Colour", validators=[Optional(), Length(min=7, max=7)], default="#6c63ff")
    new_password = PasswordField("Reset password (leave blank to keep current)", validators=[Optional(), Length(min=8)])
