from datetime import datetime, timedelta
import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import (
    db, User, Organization, SubscriptionPlan, Farm, Location, 
    Role, StaffMembership, UserInvitation
)
from app.forms import LoginForm, RegisterForm, StaffRegisterForm, InvitationAcceptForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    return _login('all')


@auth_bp.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    return _login('staff')


@auth_bp.route('/owner/login', methods=['GET', 'POST'])
def owner_login():
    return _login('owner')


@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    return _login('admin')


def _login(account_type):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            has_farm_admin_role = any(
                membership.role and membership.role.code == 'ADMIN'
                for membership in user.get_memberships(active_only=True)
            )
            if account_type == 'owner' and not user.is_organization_owner:
                flash('Invalid username or password for this login.', 'danger')
                return render_template('auth/login.html', form=form, login_type=account_type)
            if account_type == 'admin' and not (
                (user.is_organization_admin and not user.is_organization_owner) or has_farm_admin_role
            ):
                flash('Invalid username or password for this login.', 'danger')
                return render_template('auth/login.html', form=form, login_type=account_type)
            if account_type == 'staff' and not user.is_platform_admin and (
                user.is_organization_owner or user.is_organization_admin or has_farm_admin_role
            ):
                flash('Invalid username or password for this login.', 'danger')
                return render_template('auth/login.html', form=form, login_type=account_type)

            # Check if user's organization has active subscription
            if user.organization_id:
                org = db.session.get(Organization, user.organization_id)
                if not org or not org.is_subscription_active():
                    flash('Your organization subscription has expired. Please contact your organization owner.', 'danger')
                    return render_template('auth/login.html', form=form)
            
            login_user(user, remember=form.remember.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.full_name}!', 'success')
            
            # Platform admin goes to platform admin dashboard
            if user.is_platform_admin:
                return redirect(next_page or url_for('platform_admin.dashboard'))
            
            # Redirect to onboarding if organization setup not completed
            if (user.is_organization_owner or user.is_organization_admin) and user.organization:
                org = user.organization
                if not org.setup_completed:
                    return redirect(url_for('onboarding.setup_wizard'))
            
            # Organization owners and admins go to farm selection/dashboard
            if user.is_organization_owner or user.is_organization_admin:
                return redirect(next_page or url_for('main.select_farm'))
            
            # Regular staff members go directly to farm dashboard if they have one farm
            # or to farm selection if they have multiple farms
            try:
                memberships = user.get_memberships(active_only=True)
                if len(memberships) == 1:
                    session['current_farm_id'] = memberships[0].farm_id
                    return redirect(url_for('main.dashboard'))
                elif len(memberships) > 1:
                    return redirect(url_for('main.select_farm'))
                else:
                    # No farm access yet
                    flash('You have not been assigned to any farm yet. Please wait for your administrator to assign you.', 'info')
                    return redirect(url_for('main.no_access'))
            except Exception as e:
                # Fallback for staff without get_memberships method or other errors
                flash('You have not been assigned to any farm yet. Please wait for your administrator to assign you.', 'info')
                return redirect(url_for('main.no_access'))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html', form=form, login_type=account_type)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Organization owner registration - creates new organization and owner user."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        # Get the default trial plan
        trial_plan = SubscriptionPlan.query.filter_by(slug='trial').first()
        if not trial_plan:
            trial_plan = SubscriptionPlan.query.first()  # Fallback to any plan
        
        # Create the user first (without organization)
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            is_active=True,
            is_organization_owner=True,
            is_organization_admin=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # Get user.id without committing
        
        # Create the organization with this user as owner
        trial_ends = datetime.utcnow() + timedelta(days=trial_plan.trial_days if trial_plan else 14)
        organization = Organization(
            name=form.organization_name.data,
            slug=form.organization_slug.data,
            owner_id=user.id,
            business_email=form.email.data,
            country=form.country.data,
            subscription_plan_id=trial_plan.id if trial_plan else None,
            subscription_status='TRIAL',
            trial_ends_at=trial_ends,
            max_farms=trial_plan.max_farms if trial_plan else 1,
            max_animals=trial_plan.max_animals if trial_plan else 50,
            max_staff=trial_plan.max_staff if trial_plan else 3,
            is_active=True,
            setup_completed=False,
        )
        db.session.add(organization)
        db.session.flush()
        
        # Link user to organization
        user.organization_id = organization.id
        
        db.session.commit()
        
        flash(f'Welcome to FarmIt! Your trial account has been created. You have {trial_plan.trial_days if trial_plan else 14} days to explore.', 'success')
        
        # Log the user in
        login_user(user)
        
        # Redirect to setup wizard
        return redirect(url_for('onboarding.setup_wizard'))
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/register/staff', methods=['GET', 'POST'])
def register_staff():
    """Register staff in an existing organization without granting farm access."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = StaffRegisterForm()
    if form.validate_on_submit():
        organization = Organization.query.filter_by(
            slug=form.organization_slug.data.strip().lower()
        ).first()
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            organization_id=organization.id,
            is_active=True,
            is_organization_owner=False,
            is_organization_admin=False,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Your account is ready. Your organization owner must assign you to a farm before you can use FarmIt.', 'info')
        return redirect(url_for('main.no_access'))

    return render_template('auth/staff_register.html', form=form)


@auth_bp.route('/invitation/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    """Accept an invitation to join an organization."""
    invitation = UserInvitation.query.filter_by(token=token).first()
    
    if not invitation:
        flash('Invalid invitation link.', 'danger')
        return redirect(url_for('auth.login'))
    
    if not invitation.is_valid():
        flash('This invitation has expired or has already been accepted.', 'warning')
        return redirect(url_for('auth.login'))
    
    # Check if user with this email already exists
    existing_user = User.query.filter_by(email=invitation.email).first()
    if existing_user:
        flash('An account with this email already exists. Please login instead.', 'info')
        return redirect(url_for('auth.login'))
    
    form = InvitationAcceptForm()
    
    if form.validate_on_submit():
        # Create the user
        user = User(
            username=form.username.data,
            email=invitation.email,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            organization_id=invitation.organization_id,
            is_active=True,
            is_organization_owner=False,
            is_organization_admin=invitation.role_code == 'ADMIN',
            invited_by=invitation.invited_by,
            invitation_accepted_at=datetime.utcnow(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        
        # Update invitation status
        invitation.status = 'ACCEPTED'
        invitation.accepted_at = datetime.utcnow()
        invitation.accepted_by_user_id = user.id
        
        # Create staff memberships for assigned farms
        if invitation.farm_ids and invitation.role_code:
            role = Role.query.filter_by(code=invitation.role_code).first()
            if role:
                for farm_id in invitation.farm_ids:
                    membership = StaffMembership(
                        user_id=user.id,
                        farm_id=farm_id,
                        role_id=role.id,
                        joining_date=datetime.utcnow().date(),
                        is_active=True,
                    )
                    db.session.add(membership)
        
        db.session.commit()
        
        flash('Your account has been created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    # Pre-fill email from invitation
    organization = db.session.get(Organization, invitation.organization_id)
    
    return render_template('auth/accept_invitation.html', 
                         form=form, 
                         invitation=invitation,
                         organization=organization)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
