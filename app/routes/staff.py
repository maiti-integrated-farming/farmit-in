from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user
from app.models import db, StaffMembership, User, Role, Farm
from app.forms import StaffInviteForm
from app.decorators import farm_required, permission_required, role_required
from datetime import datetime, date

staff_bp = Blueprint('staff', __name__)


@staff_bp.route('/')
@login_required
@farm_required
@permission_required('view_staff')
def list_staff():
    farm_id = session['current_farm_id']
    memberships = StaffMembership.query.filter_by(farm_id=farm_id).order_by(
        StaffMembership.is_active.desc(), StaffMembership.created_at.desc()
    ).all()
    return render_template('staff/list.html', memberships=memberships)


@staff_bp.route('/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_staff')
def add_staff():
    farm_id = session['current_farm_id']
    form = StaffInviteForm()
    form.role_id.choices = [(r.id, r.name) for r in Role.query.order_by(Role.name).all()]
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            flash('User not found. They must register first.', 'danger')
            return render_template('staff/form.html', form=form, title='Add Staff')
        existing = StaffMembership.query.filter_by(user_id=user.id, farm_id=farm_id).first()
        if existing:
            if existing.is_active:
                flash('User is already a staff member of this farm.', 'warning')
            else:
                existing.is_active = True
                existing.deactivated_at = None
                existing.role_id = form.role_id.data
                existing.staff_code = form.staff_code.data
                existing.designation = form.designation.data
                existing.joining_date = form.joining_date.data or date.today()
                existing.remarks = form.remarks.data
                db.session.commit()
                flash('Staff membership reactivated.', 'success')
            return redirect(url_for('staff.list_staff'))
        membership = StaffMembership(
            user_id=user.id,
            farm_id=farm_id,
            role_id=form.role_id.data,
            staff_code=form.staff_code.data,
            designation=form.designation.data,
            joining_date=form.joining_date.data or date.today(),
            is_active=True,
            remarks=form.remarks.data,
        )
        db.session.add(membership)
        db.session.commit()
        flash(f'{user.full_name} added as staff.', 'success')
        return redirect(url_for('staff.list_staff'))
    return render_template('staff/form.html', form=form, title='Add Staff Member')


@staff_bp.route('/<int:id>/deactivate', methods=['POST'])
@login_required
@farm_required
@permission_required('manage_staff')
def deactivate_staff(id):
    farm_id = session['current_farm_id']
    membership = StaffMembership.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    if membership.user_id == current_user.id:
        flash('You cannot deactivate yourself.', 'danger')
        return redirect(url_for('staff.list_staff'))
    membership.is_active = False
    membership.deactivated_at = datetime.utcnow()
    db.session.commit()
    flash('Staff membership deactivated.', 'info')
    return redirect(url_for('staff.list_staff'))


@staff_bp.route('/<int:id>/change-role', methods=['POST'])
@login_required
@farm_required
@permission_required('manage_staff')
def change_role(id):
    farm_id = session['current_farm_id']
    membership = StaffMembership.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    new_role_id = request.form.get('role_id', type=int)
    role = Role.query.get(new_role_id)
    if role:
        membership.role_id = role.id
        db.session.commit()
        flash(f'Role updated to {role.name}.', 'success')
    return redirect(url_for('staff.list_staff'))
