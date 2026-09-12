from datetime import date

import pytest

from app import create_app
from app.extensions import db as _db
from config import TestConfig
from app.models import Household, User, Category
from app.models.user import ROLE_ADMIN, ROLE_MEMBER
from app.models.category import TYPE_INCOME, TYPE_EXPENSE


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def household(db):
    hh = Household(name="Test Household")
    db.session.add(hh)
    db.session.commit()
    return hh


@pytest.fixture()
def salary_category(db, household):
    cat = Category(household_id=household.id, name="Salary", type=TYPE_INCOME, color="#8b7bff")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def groceries_category(db, household):
    cat = Category(household_id=household.id, name="Groceries", type=TYPE_EXPENSE, color="#229954")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def admin_user(db, household):
    user = User(household_id=household.id, email="admin@example.com", display_name="Ada Admin", role=ROLE_ADMIN)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def member_user(db, household):
    user = User(household_id=household.id, email="member@example.com", display_name="Mel Member", role=ROLE_MEMBER)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)
