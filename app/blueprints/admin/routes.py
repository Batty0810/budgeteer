from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User
from app.utils.decorators import admin_required
from app.blueprints.admin.forms import NewUserForm, EditUserForm, HouseholdSettingsForm

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/users")
@login_required
@admin_required
def users():
    household_users = (
        User.query.filter_by(household_id=current_user.household_id).order_by(User.created_at.asc()).all()
    )
    return render_template("admin/users.html", users=household_users)


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_user():
    form = NewUserForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("A user with that email already exists.", "error")
        else:
            user = User(
                household_id=current_user.household_id,
                display_name=form.display_name.data.strip(),
                email=email,
                role=form.role.data,
                color=form.color.data or "#6c63ff",
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash(f"Created login for {user.display_name}. Share the temporary password securely.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", form=form, mode="new")


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.household_id != current_user.household_id:
        abort(404)

    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != user.id:
            flash("A user with that email already exists.", "error")
        else:
            user.display_name = form.display_name.data.strip()
            user.email = email
            user.role = form.role.data
            user.color = form.color.data or user.color
            if form.new_password.data:
                user.set_password(form.new_password.data)
            db.session.commit()
            flash(f"Updated {user.display_name}.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", form=form, mode="edit", user=user)


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_active(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.household_id != current_user.household_id:
        abort(404)
    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "error")
        return redirect(url_for("admin.users"))

    user.is_active_flag = not user.is_active_flag
    db.session.commit()
    state = "activated" if user.is_active_flag else "deactivated"
    flash(f"{user.display_name} has been {state}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/household", methods=["GET", "POST"])
@login_required
@admin_required
def household_settings():
    household = current_user.household
    form = HouseholdSettingsForm(obj=household)
    if form.validate_on_submit():
        household.name = form.name.data.strip()
        household.period_start_day = form.period_start_day.data
        db.session.commit()
        flash("Household settings saved.", "success")
        return redirect(url_for("admin.household_settings"))
    return render_template("admin/household.html", form=form)
