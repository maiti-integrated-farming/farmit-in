from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Organization, Farm, Location, Role, StaffMembership
from app.forms import FarmForm, LocationForm
from app.decorators import farm_required

onboarding_bp = Blueprint('onboarding', __name__)


@onboarding_bp.route('/setup-wizard', methods=['GET', 'POST'])
@login_required
def setup_wizard():
    """Initial setup wizard for new organization owners and admins."""
    if not (current_user.is_organization_owner or current_user.is_organization_admin):
        flash('Only organization owners and administrators can access the setup wizard.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('auth.logout'))
    
    if org.setup_completed:
        return redirect(url_for('main.select_farm'))
    
    # Check if they have at least one farm
    has_farm = Farm.query.filter_by(organization_id=org.id).first() is not None
    
    return render_template('onboarding/setup_wizard.html', 
                         organization=org,
                         has_farm=has_farm)


@onboarding_bp.route('/setup/farm', methods=['GET', 'POST'])
@login_required
def setup_farm():
    """Create a farm for the current owner's organization."""
    if not current_user.is_organization_owner:
        flash('Only the organization owner can create farms.', 'danger')
        return redirect(url_for('main.select_farm'))
    
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # Check if they can add more farms
    if not org.can_add_farm():
        flash(f'An organization can have a maximum of {org.farm_limit} farms.', 'warning')
        return redirect(url_for('main.select_farm'))
    
    form = FarmForm()
    
    if form.validate_on_submit():
        # Check for duplicate code within organization
        existing = Farm.query.filter_by(
            organization_id=org.id,
            code=form.code.data
        ).first()
        
        if existing:
            flash('A farm with this code already exists in your organization.', 'danger')
        else:
            farm = Farm(
                organization_id=org.id,
                name=form.name.data,
                code=form.code.data,
                address=form.address.data,
                contact_phone=form.contact_phone.data,
                status=form.status.data,
            )
            db.session.add(farm)
            db.session.flush()
            
            # Create default locations
            default_locations = [
                Location(farm_id=farm.id, name='Main Shed', capacity=50, is_active=True),
                Location(farm_id=farm.id, name='Quarantine Area', capacity=10, is_active=True),
            ]
            for loc in default_locations:
                db.session.add(loc)
            
            # Add owner as OWNER role member of this farm
            owner_role = Role.query.filter_by(code='OWNER').first()
            if owner_role:
                membership = StaffMembership(
                    user_id=current_user.id,
                    farm_id=farm.id,
                    role_id=owner_role.id,
                    staff_code='OWNER001',
                    designation='Farm Owner',
                    joining_date=date.today(),
                    is_active=True,
                )
                db.session.add(membership)
            
            db.session.commit()
            
            flash(f'Farm "{farm.name}" created successfully!', 'success')
            if org.setup_completed:
                return redirect(url_for('main.select_farm'))
            return redirect(url_for('onboarding.setup_complete'))
    
    return render_template('onboarding/setup_farm.html', form=form, organization=org,
                           farm_count=org.farms.count())


@onboarding_bp.route('/setup/complete', methods=['GET', 'POST'])
@login_required
def setup_complete():
    """Mark setup as complete and redirect to dashboard."""
    if not (current_user.is_organization_owner or current_user.is_organization_admin):
        flash('Only organization owners and administrators can complete setup.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # Verify they have at least one farm
    farm_count = Farm.query.filter_by(organization_id=org.id).count()
    if farm_count == 0:
        flash('Please create at least one farm to complete setup.', 'warning')
        return redirect(url_for('onboarding.setup_farm'))
    
    if not org.setup_completed:
        org.setup_completed = True
        db.session.commit()
        flash('Setup completed! Welcome to FarmIt.', 'success')
    
    return redirect(url_for('main.select_farm'))
