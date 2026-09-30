from functools import wraps
from flask import abort, session, flash, redirect, url_for
from flask_login import current_user


def organization_required(f):
    """Ensure user belongs to an organization with active subscription."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # Platform admins bypass organization checks
        if current_user.is_platform_admin:
            return f(*args, **kwargs)
        
        # Check if user has an organization
        if not current_user.organization_id:
            flash('You are not associated with any organization.', 'danger')
            return redirect(url_for('auth.logout'))
        
        # Check if organization subscription is active
        org = current_user.organization
        if not org or not org.is_subscription_active():
            flash('Your organization subscription has expired. Please contact your organization owner.', 'warning')
            return redirect(url_for('auth.logout'))
        
        return f(*args, **kwargs)
    return decorated


def farm_required(f):
    """Ensure user is logged in, has organization access, and has a selected farm."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # Platform admins can access any farm
        if current_user.is_platform_admin:
            farm_id = session.get('current_farm_id')
            if not farm_id:
                flash('Please select a farm to continue.', 'warning')
                return redirect(url_for('main.select_farm'))
            return f(*args, **kwargs)
        
        # Check organization membership and subscription
        if not current_user.organization_id:
            flash('You are not associated with any organization.', 'danger')
            return redirect(url_for('auth.logout'))
        
        org = current_user.organization
        if not org or not org.is_subscription_active():
            flash('Your organization subscription has expired or is inactive.', 'warning')
            return redirect(url_for('auth.logout'))
        
        # Check farm selection and access
        farm_id = session.get('current_farm_id')
        if not farm_id:
            flash('Please select a farm to continue.', 'warning')
            return redirect(url_for('main.select_farm'))
        
        # Verify farm belongs to user's organization and user has access
        if not current_user.has_farm_access(farm_id):
            flash('Access denied to this farm.', 'danger')
            session.pop('current_farm_id', None)
            return redirect(url_for('main.select_farm'))
        
        return f(*args, **kwargs)
    return decorated


def permission_required(codename):
    """Require a specific permission for the current farm with tenant isolation."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Platform admins have all permissions
            if current_user.is_platform_admin:
                return f(*args, **kwargs)
            
            # Check organization
            if not current_user.organization_id:
                flash('You are not associated with any organization.', 'danger')
                return redirect(url_for('auth.logout'))
            
            org = current_user.organization
            if not org or not org.is_subscription_active():
                flash('Your organization subscription is not active.', 'warning')
                return redirect(url_for('auth.logout'))
            
            # Check farm selection
            farm_id = session.get('current_farm_id')
            if not farm_id:
                flash('Please select a farm.', 'warning')
                return redirect(url_for('main.select_farm'))
            
            # Verify tenant isolation - farm must belong to user's organization
            from app.models import Farm, db
            farm = db.session.get(Farm, farm_id)
            if not farm or farm.organization_id != current_user.organization_id:
                flash('Access denied to this farm.', 'danger')
                session.pop('current_farm_id', None)
                return redirect(url_for('main.select_farm'))
            
            # Check permission
            if not current_user.has_permission(farm_id, codename):
                flash('You do not have permission to perform this action.', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated
    return decorator


def role_required(*role_codes):
    """Require one of the given roles for the current farm with tenant isolation."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Platform admins bypass role checks
            if current_user.is_platform_admin:
                return f(*args, **kwargs)
            
            # Check organization
            if not current_user.organization_id:
                flash('You are not associated with any organization.', 'danger')
                return redirect(url_for('auth.logout'))
            
            org = current_user.organization
            if not org or not org.is_subscription_active():
                flash('Your organization subscription is not active.', 'warning')
                return redirect(url_for('auth.logout'))
            
            # Check farm selection
            farm_id = session.get('current_farm_id')
            if not farm_id:
                flash('Please select a farm.', 'warning')
                return redirect(url_for('main.select_farm'))
            
            # Verify tenant isolation
            from app.models import Farm, db
            farm = db.session.get(Farm, farm_id)
            if not farm or farm.organization_id != current_user.organization_id:
                flash('Access denied to this farm.', 'danger')
                session.pop('current_farm_id', None)
                return redirect(url_for('main.select_farm'))
            
            # Organization owners have all role privileges
            if current_user.is_organization_owner:
                return f(*args, **kwargs)
            
            # Check role
            role = current_user.get_role_for_farm(farm_id)
            if not role or role.code not in role_codes:
                flash('Insufficient role privileges.', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated
    return decorator


def platform_admin_required(f):
    """Require platform admin access (super admin)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.is_platform_admin:
            flash('Platform administrator access required.', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated


def organization_owner_required(f):
    """Require organization owner access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.is_organization_owner and not current_user.is_platform_admin:
            flash('Organization owner access required.', 'danger')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated
