from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField
from wtforms.validators import Optional, Length


class UploadStatementForm(FlaskForm):
    statement = FileField(
        "Bank statement (PDF)",
        validators=[FileRequired(), FileAllowed(["pdf"], "PDF files only")],
    )
    password = StringField(
        "PDF password (if it's protected)",
        validators=[Optional(), Length(max=100)],
    )
