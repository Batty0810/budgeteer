from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.bill import IrregularBill
from app.models.category import Category
from app.blueprints.bills.forms import IrregularBillForm

bp = Blueprint("bills", __name__, url_prefix="/bills")


def _populate_category_choices(form, include_category=None):
    categories = (
        Category.query.filter_by(household_id=current_user.household_id, is_archived=False)
        .order_by(Category.name.asc())
        .all()
    )
    # Keep a since-archived category selectable when editing a bill that
    # still points at it, so the form doesn't reject its own rendered value.
    if include_category and include_category.is_archived and include_category not in categories:
        categories = categories + [include_category]
    form.category_id.choices = [
        (c.id, c.name + (" - archived" if c.is_archived else "")) for c in categories
    ]


@bp.route("/")
@login_required
def list_bills():
    bills = (
        IrregularBill.query.filter_by(household_id=current_user.household_id, is_active=True)
        .order_by(IrregularBill.due_date.asc())
        .all()
    )
    total_monthly_buffer = sum((b.monthly_buffer for b in bills), start=0)
    return render_template("bills/list.html", bills=bills, total_monthly_buffer=total_monthly_buffer)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_bill():
    form = IrregularBillForm()
    _populate_category_choices(form)
    if form.validate_on_submit():
        bill = IrregularBill(
            household_id=current_user.household_id,
            category_id=form.category_id.data,
            name=form.name.data.strip(),
            amount=form.amount.data,
            due_date=form.due_date.data,
            recurrence_months=form.recurrence_months.data,
        )
        db.session.add(bill)
        db.session.commit()
        flash(f"Added irregular bill {bill.name!r}. Set aside {bill.monthly_buffer:.2f} a month for it.", "success")
        return redirect(url_for("bills.list_bills"))
    return render_template("bills/form.html", form=form, mode="new")


@bp.route("/<int:bill_id>/edit", methods=["GET", "POST"])
@login_required
def edit_bill(bill_id):
    bill = db.session.get(IrregularBill, bill_id)
    if bill is None or bill.household_id != current_user.household_id:
        abort(404)
    form = IrregularBillForm(obj=bill)
    _populate_category_choices(form, include_category=bill.category)
    if form.validate_on_submit():
        bill.name = form.name.data.strip()
        bill.category_id = form.category_id.data
        bill.amount = form.amount.data
        bill.due_date = form.due_date.data
        bill.recurrence_months = form.recurrence_months.data
        db.session.commit()
        flash(f"Updated {bill.name!r}.", "success")
        return redirect(url_for("bills.list_bills"))
    return render_template("bills/form.html", form=form, mode="edit", bill=bill)


@bp.route("/<int:bill_id>/add-buffer", methods=["POST"])
@login_required
def add_buffer(bill_id):
    bill = db.session.get(IrregularBill, bill_id)
    if bill is None or bill.household_id != current_user.household_id:
        abort(404)
    bill.saved_amount = (bill.saved_amount or 0) + bill.monthly_buffer
    db.session.commit()
    flash(f"Set aside {bill.monthly_buffer:.2f} toward {bill.name!r}.", "success")
    return redirect(url_for("bills.list_bills"))


@bp.route("/<int:bill_id>/delete", methods=["POST"])
@login_required
def delete_bill(bill_id):
    bill = db.session.get(IrregularBill, bill_id)
    if bill is None or bill.household_id != current_user.household_id:
        abort(404)
    db.session.delete(bill)
    db.session.commit()
    flash("Irregular bill removed.", "info")
    return redirect(url_for("bills.list_bills"))
