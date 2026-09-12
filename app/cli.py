import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Household, User
from app.models.user import ROLE_ADMIN
from app.models.category import Category, TYPE_INCOME, TYPE_EXPENSE
from app.utils.charts import next_category_color

DEFAULT_CATEGORIES = [
    ("Salary", TYPE_INCOME),
    ("Side Hustle", TYPE_INCOME),
    ("Rent / Bond", TYPE_EXPENSE),
    ("Utilities", TYPE_EXPENSE),
    ("Groceries", TYPE_EXPENSE),
    ("Transport", TYPE_EXPENSE),
    ("Entertainment", TYPE_EXPENSE),
    ("Medical", TYPE_EXPENSE),
    ("Other", TYPE_EXPENSE),
]


@click.command("create-admin")
@click.option("--household", prompt="Household name", help="Name for the new household, e.g. 'The Smiths'.")
@click.option("--name", prompt="Your name", help="Display name for the admin account.")
@click.option("--email", prompt="Email", help="Login email for the admin account.")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_admin(household, name, email, password):
    """Bootstrap the first household and its admin user."""
    if User.query.filter_by(email=email.lower().strip()).first():
        click.echo(f"A user with email {email} already exists.")
        return

    hh = Household(name=household)
    db.session.add(hh)
    db.session.flush()

    for cat_name, cat_type in DEFAULT_CATEGORIES:
        db.session.add(
            Category(
                household_id=hh.id,
                name=cat_name,
                type=cat_type,
                color=next_category_color(Category.query.filter_by(household_id=hh.id).count()),
            )
        )

    user = User(
        household_id=hh.id,
        email=email.lower().strip(),
        display_name=name,
        role=ROLE_ADMIN,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    click.echo(f"Created household {household!r} and admin user {email!r}. You can log in now.")


def register_cli(app):
    app.cli.add_command(create_admin)
