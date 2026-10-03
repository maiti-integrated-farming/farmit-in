from datetime import datetime, timedelta
import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import (
    db, Organization, User, UserInvitation, Farm, StaffMembership, 
    Role, Subscription, SubscriptionPlan
)
from app.forms import InviteUserForm
from sqlalchemy import func

organization_bp = Blueprint('organization', __name__)


def organization_owner_required(f):
    """Decorator to ensure user is organization owner."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_organization_owner:
            flash('Only organization owners can access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@organization_bp.route('/settings')
@login_required
@organization_owner_required
def settings():
    """Organization settings dashboard."""
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get statistics
    total_farms = Farm.query.filter_by(organization_id=org.id).count()
    total_members = User.query.filter_by(organization_id=org.id, is_active=True).count()
    
    from app.models import Animal
    total_animals = db.session.query(func.count(Animal.id)).join(Farm).filter(
        Farm.organization_id == org.id,
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).scalar() or 0
    
    # Get current subscription
    current_subscription = Subscription.query.filter_by(
        organization_id=org.id,
        status='ACTIVE'
    ).order_by(Subscription.ends_at.desc()).first()
    
    # Calculate days remaining
    days_remaining = None
    if org.subscription_status == 'TRIAL' and org.trial_ends_at:
        days_remaining = (org.trial_ends_at - datetime.utcnow()).days
    elif org.subscription_ends_at:
        days_remaining = (org.subscription_ends_at - datetime.utcnow()).days
    
    return render_template('organization/settings.html',
                         organization=org,
                         total_farms=total_farms,
                         total_members=total_members,
                         total_animals=total_animals,
                         current_subscription=current_subscription,
                         days_remaining=days_remaining)


@organization_bp.route('/settings/profile', methods=['GET', 'POST'])
@login_required
@organization_owner_required
def profile():
    """Update organization profile."""
    from app.forms import OrganizationProfileForm
    
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = OrganizationProfileForm(original_slug=org.slug, obj=org)
    
    if form.validate_on_submit():
        org.name = form.name.data
        org.slug = form.slug.data
        org.contact_email = form.contact_email.data
        org.contact_phone = form.contact_phone.data
        org.address = form.address.data
        org.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Organization profile updated successfully.', 'success')
        return redirect(url_for('organization.settings'))
    
    return render_template('organization/profile.html', form=form, organization=org)


@organization_bp.route('/members')
@login_required
@organization_owner_required
def members():
    """List all organization members."""
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    members = User.query.filter_by(organization_id=org.id).order_by(User.date_joined.desc()).all()
    pending_staff_ids = {
        member.id for member in members
        if member.is_active and not member.is_organization_owner and not member.get_memberships(active_only=True)
    }
    
    # Get pending invitations
    pending_invitations = UserInvitation.query.filter_by(
        organization_id=org.id,
        status='PENDING'
    ).filter(UserInvitation.expires_at > datetime.utcnow()).all()
    
    return render_template('organization/members.html',
                         organization=org,
                         members=members,
                         pending_staff_ids=pending_staff_ids,
                         pending_invitations=pending_invitations)


@organization_bp.route('/invite', methods=['GET', 'POST'])
@login_required
@organization_owner_required
def invite_user():
    """Invite a new user to the organization."""
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check if organization can add more staff
    if not org.can_add_staff():
        flash('You have reached the maximum number of staff members for your plan. Please upgrade.', 'warning')
        return redirect(url_for('organization.members'))
    
    form = InviteUserForm()
    
    # Populate role choices
    roles = Role.query.filter(Role.code != 'OWNER').all()
    form.role_id.choices = [(r.id, r.name) for r in roles]
    
    # Populate farm choices
    farms = Farm.query.filter_by(organization_id=org.id, status='ACTIVE').all()
    form.farm_ids.choices = [(0, 'All Farms')] + [(f.id, f.name) for f in farms]
    
    if form.validate_on_submit():
        # Generate unique token
        token = secrets.token_urlsafe(32)
        
        # Get selected role
        role = db.session.get(Role, form.role_id.data)
        
        # Get farm IDs (all farms if 0 selected)
        farm_id_list = [f.id for f in farms] if form.farm_ids.data == 0 else [form.farm_ids.data]
        
        # Create invitation
        invitation = UserInvitation(
            organization_id=org.id,
            email=form.email.data,
            token=token,
            invited_by=current_user.id,
            role_code=role.code if role else None,
            farm_ids=farm_id_list,
            status='PENDING',
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(invitation)
        db.session.commit()
        
        # In a real app, send email here
        invitation_url = url_for('auth.accept_invitation', token=token, _external=True)
        
        flash(f'Invitation sent to {form.email.data}. Share this link: {invitation_url}', 'success')
        return redirect(url_for('organization.members'))
    
    return render_template('organization/invite_user.html',
                         form=form,
                         organization=org)


@organization_bp.route('/invitation/<int:invitation_id>/cancel', methods=['POST'])
@login_required
@organization_owner_required
def cancel_invitation(invitation_id):
    """Cancel a pending invitation."""
    invitation = UserInvitation.query.get_or_404(invitation_id)
    
    # Verify ownership
    if invitation.organization_id != current_user.organization_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('organization.members'))
    
    invitation.status = 'CANCELLED'
    db.session.commit()
    
    flash('Invitation cancelled.', 'success')
    return redirect(url_for('organization.members'))


@organization_bp.route('/members/<int:user_id>/deactivate', methods=['POST'])
@login_required
@organization_owner_required
def deactivate_member(user_id):
    """Deactivate a member (soft delete)."""
    user = User.query.get_or_404(user_id)
    
    # Verify user belongs to organization
    if user.organization_id != current_user.organization_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('organization.members'))
    
    # Cannot deactivate owner
    if user.is_organization_owner:
        flash('Cannot deactivate organization owner.', 'danger')
        return redirect(url_for('organization.members'))
    
    user.is_active = False
    
    # Deactivate all their farm memberships
    StaffMembership.query.filter_by(user_id=user.id, is_active=True).update({
        'is_active': False,
        'deactivated_at': datetime.utcnow()
    })
    
    db.session.commit()
    
    flash(f'User {user.full_name} has been deactivated.', 'success')
    return redirect(url_for('organization.members'))


@organization_bp.route('/subscription')
@login_required
@organization_owner_required
def subscription():
    """View subscription details and upgrade options."""
    org = current_user.organization
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get all available plans
    available_plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.sort_order).all()
    
    # Get current plan
    current_plan = None
    if org.current_plan:
        current_plan = SubscriptionPlan.query.filter_by(name=org.current_plan).first()
    
    # Calculate days remaining
    days_remaining = None
    if org.subscription_status == 'TRIAL' and org.trial_ends_at:
        days_remaining = (org.trial_ends_at - datetime.utcnow()).days
    elif org.subscription_end_date:
        days_remaining = (org.subscription_end_date - datetime.utcnow()).days
    
    return render_template('organization/subscription.html',
                         organization=org,
                         available_plans=available_plans,
                         current_plan=current_plan,
                         days_remaining=days_remaining)


@organization_bp.route('/subscription/upgrade/<int:plan_id>', methods=['POST'])
@login_required
@organization_owner_required
def upgrade_plan(plan_id):
    """Upgrade to a new subscription plan."""
    org = current_user.organization
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    
    if not org:
        flash('Organization not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Update organization with new plan limits
    org.current_plan = plan.name
    org.subscription_status = 'ACTIVE'
    org.subscription_start_date = datetime.utcnow()
    org.subscription_end_date = datetime.utcnow() + timedelta(days=365 if plan.billing_period == 'year' else 30)
    org.max_farms = plan.max_farms
    org.max_animals = plan.max_animals
    org.max_staff = plan.max_staff
    org.storage_limit_gb = plan.storage_limit_gb
    org.auto_renew = True
    org.updated_at = datetime.utcnow()
    
    # Create subscription record
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status='ACTIVE',
        starts_at=org.subscription_start_date,
        ends_at=org.subscription_end_date,
        amount=plan.price_amount,
        currency=plan.price_currency,
        billing_cycle='YEARLY' if plan.billing_period == 'year' else 'MONTHLY'
    )
    db.session.add(subscription)
    db.session.commit()
    
    flash(f'Successfully upgraded to {plan.name}!', 'success')
    return redirect(url_for('organization.subscription'))
