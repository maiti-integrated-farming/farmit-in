"""
Subscription and feature limits enforcement for SaaS.
"""
from flask import flash, redirect, url_for
from flask_login import current_user
from functools import wraps


class LimitExceeded(Exception):
    """Exception raised when a subscription limit is exceeded."""
    def __init__(self, message, limit_type):
        self.message = message
        self.limit_type = limit_type
        super().__init__(self.message)


def check_farm_limit():
    """Check if organization can add more farms."""
    if current_user.is_platform_admin:
        return True
    
    org = current_user.organization
    if not org:
        raise LimitExceeded('Organization not found.', 'organization')
    
    if not org.can_add_farm():
        raise LimitExceeded(
            f'You have reached the maximum number of farms ({org.farm_limit}) for your organization.',
            'farms'
        )
    return True


def check_animal_limit():
    """Check if organization can add more animals."""
    if current_user.is_platform_admin:
        return True
    
    org = current_user.organization
    if not org:
        raise LimitExceeded('Organization not found.', 'organization')
    
    if not org.can_add_animal():
        raise LimitExceeded(
            f'You have reached the maximum number of animals ({org.max_animals}) for your plan. Please upgrade.',
            'animals'
        )
    return True


def check_staff_limit():
    """Check if organization can add more staff."""
    if current_user.is_platform_admin:
        return True
    
    org = current_user.organization
    if not org:
        raise LimitExceeded('Organization not found.', 'organization')
    
    if not org.can_add_staff():
        raise LimitExceeded(
            f'You have reached the maximum number of staff members ({org.max_staff}) for your plan. Please upgrade.',
            'staff'
        )
    return True


def check_subscription_active():
    """Check if organization has an active subscription."""
    if current_user.is_platform_admin:
        return True
    
    org = current_user.organization
    if not org:
        raise LimitExceeded('Organization not found.', 'organization')
    
    if not org.is_subscription_active():
        raise LimitExceeded(
            'Your organization subscription has expired. Please renew your subscription.',
            'subscription'
        )
    return True


def require_feature(feature_name):
    """Decorator to check if a feature is enabled for the organization's plan."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if current_user.is_platform_admin:
                return f(*args, **kwargs)
            
            org = current_user.organization
            if not org or not org.subscription_plan_id:
                flash('Feature not available. Please subscribe to a plan.', 'warning')
                return redirect(url_for('organization.subscription'))
            
            plan = org.plan
            if plan and plan.features_json:
                features = plan.features_json
                if not features.get(feature_name, False):
                    flash(f'This feature is not included in your current plan. Please upgrade.', 'warning')
                    return redirect(url_for('organization.subscription'))
            
            return f(*args, **kwargs)
        return decorated
    return decorator


def enforce_limit(limit_type):
    """Decorator to enforce a specific limit before executing the function."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                if limit_type == 'farm':
                    check_farm_limit()
                elif limit_type == 'animal':
                    check_animal_limit()
                elif limit_type == 'staff':
                    check_staff_limit()
                elif limit_type == 'subscription':
                    check_subscription_active()
                else:
                    raise ValueError(f'Unknown limit type: {limit_type}')
                
                return f(*args, **kwargs)
            
            except LimitExceeded as e:
                flash(e.message, 'warning')
                if e.limit_type in ['farms', 'animals', 'staff', 'subscription']:
                    return redirect(url_for('organization.subscription'))
                return redirect(url_for('main.dashboard'))
        
        return decorated
    return decorator


def get_usage_stats(organization):
    """Get current usage statistics for an organization."""
    from app.models import db, Farm, Animal, User, StaffMembership
    from sqlalchemy import func
    
    # Count active farms
    farms_used = Farm.query.filter_by(organization_id=organization.id, status='ACTIVE').count()
    
    # Count active animals across all farms
    animals_used = db.session.query(func.count(Animal.id)).join(Farm).filter(
        Farm.organization_id == organization.id,
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).scalar() or 0
    
    # Count active staff across all farms (distinct users)
    staff_used = db.session.query(func.count(func.distinct(StaffMembership.user_id))).join(Farm).filter(
        Farm.organization_id == organization.id,
        StaffMembership.is_active == True
    ).scalar() or 0
    
    return {
        'farms': {
            'used': farms_used,
            'limit': organization.max_farms,
            'percentage': (farms_used / organization.max_farms * 100) if organization.max_farms > 0 else 0
        },
        'animals': {
            'used': animals_used,
            'limit': organization.max_animals,
            'percentage': (animals_used / organization.max_animals * 100) if organization.max_animals > 0 else 0
        },
        'staff': {
            'used': staff_used,
            'limit': organization.max_staff,
            'percentage': (staff_used / organization.max_staff * 100) if organization.max_staff > 0 else 0
        }
    }
