from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Farm, Role, Permission, RolePermission
from app.forms import FarmForm, RoleForm
from app.decorators import farm_required, role_required, permission_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/farm-settings', methods=['GET', 'POST'])
@login_required
@farm_required
@role_required('OWNER', 'ADMIN')
def farm_settings():
    farm_id = session['current_farm_id']
    farm = db.session.get(Farm, farm_id)
    form = FarmForm(obj=farm)
    if form.validate_on_submit():
        form.populate_obj(farm)
        db.session.commit()
        flash('Farm settings updated.', 'success')
        return redirect(url_for('admin.farm_settings'))
    return render_template('admin/farm_settings.html', form=form, farm=farm)


@admin_bp.route('/roles')
@login_required
@farm_required
@role_required('OWNER', 'ADMIN')
def list_roles():
    roles = Role.query.order_by(Role.name).all()
    return render_template('admin/roles.html', roles=roles)


@admin_bp.route('/roles/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_permissions')
def add_role():
    form = RoleForm()
    permissions = Permission.query.order_by(Permission.content_type, Permission.name).all()
    form.permission_ids.choices = [(p.id, f'{p.content_type}: {p.name}') for p in permissions]
    if form.validate_on_submit():
        if Role.query.filter_by(code=form.code.data.upper()).first():
            flash('A role with this code already exists.', 'danger')
        else:
            role = Role(code=form.code.data.upper(), name=form.name.data, description=form.description.data)
            role.permissions = Permission.query.filter(Permission.id.in_(form.permission_ids.data or [])).all()
            db.session.add(role)
            db.session.commit()
            flash('Role created.', 'success')
            return redirect(url_for('admin.list_roles'))
    return render_template('admin/role_form.html', form=form, title='Create Role')


@admin_bp.route('/roles/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_permissions')
def edit_role(id):
    role = db.session.get(Role, id)
    if not role:
        from flask import abort
        abort(404)
    form = RoleForm(obj=role)
    permissions = Permission.query.order_by(Permission.content_type, Permission.name).all()
    form.permission_ids.choices = [(p.id, f'{p.content_type}: {p.name}') for p in permissions]
    if not form.is_submitted():
        form.permission_ids.data = [permission.id for permission in role.permissions]
    if form.validate_on_submit():
        role.code = form.code.data.upper()
        role.name = form.name.data
        role.description = form.description.data
        role.permissions = Permission.query.filter(Permission.id.in_(form.permission_ids.data or [])).all()
        db.session.commit()
        flash('Role permissions updated.', 'success')
        return redirect(url_for('admin.list_roles'))
    return render_template('admin/role_form.html', form=form, title=f'Edit {role.name}')
