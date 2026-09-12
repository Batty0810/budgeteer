from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.wishlist import (
    WishlistItem,
    WishlistVote,
    WishlistContribution,
    STATUS_PROPOSED,
    STATUS_SAVING,
    STATUS_PURCHASED,
    STATUS_ARCHIVED,
    STATUS_LABELS,
)
from app.blueprints.wishlist.forms import WishlistItemForm, ContributionForm

bp = Blueprint("wishlist", __name__, url_prefix="/wishlist")


@bp.route("/")
@login_required
def list_items():
    items = (
        WishlistItem.query.filter(
            WishlistItem.household_id == current_user.household_id,
            WishlistItem.status != STATUS_ARCHIVED,
        )
        .all()
    )
    items.sort(key=lambda i: i.score, reverse=True)
    contribution_form = ContributionForm()
    return render_template(
        "wishlist/list.html",
        items=items,
        status_labels=STATUS_LABELS,
        contribution_form=contribution_form,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_item():
    form = WishlistItemForm()
    if form.validate_on_submit():
        item = WishlistItem(
            household_id=current_user.household_id,
            created_by_id=current_user.id,
            name=form.name.data.strip(),
            description=form.description.data,
            url=form.url.data,
            estimated_cost=form.estimated_cost.data,
            status=STATUS_PROPOSED,
        )
        db.session.add(item)
        db.session.commit()
        flash(f"Added {item.name!r} to the shared wishlist.", "success")
        return redirect(url_for("wishlist.list_items"))
    return render_template("wishlist/form.html", form=form, mode="new")


@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = db.session.get(WishlistItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    form = WishlistItemForm(obj=item)
    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.description = form.description.data
        item.url = form.url.data
        item.estimated_cost = form.estimated_cost.data
        db.session.commit()
        flash(f"Updated {item.name!r}.", "success")
        return redirect(url_for("wishlist.list_items"))
    return render_template("wishlist/form.html", form=form, mode="edit", item=item)


@bp.route("/<int:item_id>/vote", methods=["POST"])
@login_required
def vote(item_id):
    item = db.session.get(WishlistItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    value = 1 if request.form.get("value") == "up" else -1

    existing = WishlistVote.query.filter_by(wishlist_item_id=item.id, user_id=current_user.id).first()
    if existing and existing.value == value:
        db.session.delete(existing)  # toggle off
    elif existing:
        existing.value = value
    else:
        db.session.add(WishlistVote(wishlist_item_id=item.id, user_id=current_user.id, value=value))
    db.session.commit()
    return redirect(url_for("wishlist.list_items"))


@bp.route("/<int:item_id>/contribute", methods=["POST"])
@login_required
def contribute(item_id):
    item = db.session.get(WishlistItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    form = ContributionForm()
    if form.validate_on_submit():
        db.session.add(
            WishlistContribution(
                wishlist_item_id=item.id,
                user_id=current_user.id,
                amount=form.amount.data,
                note=form.note.data,
            )
        )
        item.saved_amount = (item.saved_amount or 0) + form.amount.data
        if item.status == STATUS_PROPOSED:
            item.status = STATUS_SAVING
        db.session.commit()
        flash(f"Added R{form.amount.data:.2f} toward {item.name!r}.", "success")
    else:
        flash("Enter a valid amount.", "error")
    return redirect(url_for("wishlist.list_items"))


@bp.route("/<int:item_id>/status", methods=["POST"])
@login_required
def set_status(item_id):
    item = db.session.get(WishlistItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    new_status = request.form.get("status")
    if new_status in STATUS_LABELS:
        item.status = new_status
        db.session.commit()
        flash(f"{item.name} marked as {STATUS_LABELS[new_status]}.", "info")
    return redirect(url_for("wishlist.list_items"))


@bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = db.session.get(WishlistItem, item_id)
    if item is None or item.household_id != current_user.household_id:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Removed from wishlist.", "info")
    return redirect(url_for("wishlist.list_items"))
