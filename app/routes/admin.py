from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Farm, Role, Permission, RolePermission
from app.forms import FarmForm
from app.decorators import farm_required, role_required

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
