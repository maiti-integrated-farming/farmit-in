"""
Platform Admin Dashboard - For managing the entire SaaS platform.
Only accessible by users with is_platform_admin=True.
"""
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import (
    db, Organization, User, Farm, SubscriptionPlan, Subscription, 
    Animal, StaffMembership, UserInvitation
)
from app.decorators import platform_admin_required
from sqlalchemy import func, desc

platform_admin_bp = Blueprint('platform_admin', __name__)


@platform_admin_bp.route('/dashboard')
@login_required
@platform_admin_required
def dashboard():
    """Main platform admin dashboard with key metrics."""
    
    # Organization metrics
    total_organizations = Organization.query.count()
    active_organizations = Organization.query.filter_by(is_active=True).count()
    trial_organizations = Organization.query.filter_by(subscription_status='TRIAL').count()
    paid_organizations = Organization.query.filter_by(subscription_status='ACTIVE').count()
    
    # User metrics
    total_users = User.query.filter_by(is_platform_admin=False).count()
    active_users = User.query.filter_by(is_active=True, is_platform_admin=False).count()
    organization_owners = User.query.filter_by(is_organization_owner=True).count()
    
    # Farm metrics
    total_farms = Farm.query.count()
    active_farms = Farm.query.filter_by(status='ACTIVE').count()
    
    # Animal metrics
    total_animals = Animal.query.filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).count()
    
    # Recent signups (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_signups = Organization.query.filter(
        Organization.created_at >= thirty_days_ago
    ).count()
    
    # Revenue metrics (from active subscriptions)
    monthly_revenue = db.session.query(
        func.sum(Subscription.amount)
    ).filter(
        Subscription.status == 'ACTIVE',
        Subscription.billing_cycle == 'MONTHLY'
    ).scalar() or 0
    
    yearly_revenue = db.session.query(
        func.sum(Subscription.amount)
    ).filter(
        Subscription.status == 'ACTIVE',
        Subscription.billing_cycle == 'YEARLY'
    ).scalar() or 0
    
    # MRR (Monthly Recurring Revenue) - convert yearly to monthly
    mrr = float(monthly_revenue) + (float(yearly_revenue) / 12)
    
    # Subscription plan distribution
    plan_distribution = db.session.query(
        SubscriptionPlan.name,
        func.count(Organization.id)
    ).join(Organization, Organization.subscription_plan_id == SubscriptionPlan.id).group_by(
        SubscriptionPlan.name
    ).all()
    
    # Recent organizations
    recent_orgs = Organization.query.order_by(
        Organization.created_at.desc()
    ).limit(10).all()
    
    # Expiring trials (next 7 days)
    seven_days_later = datetime.utcnow() + timedelta(days=7)
    expiring_trials = Organization.query.filter(
        Organization.subscription_status == 'TRIAL',
        Organization.trial_ends_at <= seven_days_later,
        Organization.trial_ends_at >= datetime.utcnow()
    ).count()
    
    stats = {
        'total_organizations': total_organizations,
        'active_organizations': active_organizations,
        'trial_organizations': trial_organizations,
        'paid_organizations': paid_organizations,
        'total_users': total_users,
        'active_users': active_users,
        'organization_owners': organization_owners,
        'total_farms': total_farms,
        'active_farms': active_farms,
        'total_animals': total_animals,
        'recent_signups': recent_signups,
        'new_orgs_this_month': recent_signups,
        'new_users_this_month': User.query.filter(
            User.date_joined >= thirty_days_ago,
            User.is_platform_admin == False
        ).count(),
        'monthly_revenue': float(monthly_revenue),
        'yearly_revenue': float(yearly_revenue),
        'mrr': mrr,
        'revenue_growth': 0,
        'expiring_trials': expiring_trials,
        'subscription_distribution': [
            {'name': name, 'count': count,
             'percentage': round(count / max(total_organizations, 1) * 100, 1)}
            for name, count in plan_distribution
        ],
    }

    return render_template('platform_admin/dashboard.html',
                         stats=stats,
                         plan_distribution=plan_distribution,
                         recent_organizations=recent_orgs,
                         alerts=[])


@platform_admin_bp.route('/organizations')
@login_required
@platform_admin_required
def organizations():
    """List all organizations with filtering."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    query = Organization.query
    
    # Apply filters
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    elif status_filter == 'trial':
        query = query.filter_by(subscription_status='TRIAL')
    elif status_filter == 'paid':
        query = query.filter_by(subscription_status='ACTIVE')
    
    if search:
        query = query.filter(
            db.or_(
                Organization.name.ilike(f'%{search}%'),
                Organization.slug.ilike(f'%{search}%'),
                Organization.business_email.ilike(f'%{search}%')
            )
        )
    
    # Paginate
    per_page = 20
    pagination = query.order_by(Organization.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    subscription_plans = SubscriptionPlan.query.filter_by(is_active=True).all()

    return render_template('platform_admin/organizations.html',
                         organizations=pagination.items,
                         pagination=pagination,
                         subscription_plans=subscription_plans,
                         status_filter=status_filter,
                         search=search)


@platform_admin_bp.route('/organizations/<int:org_id>')
@login_required
@platform_admin_required
def organization_detail(org_id):
    """View detailed information about an organization."""
    org = Organization.query.get_or_404(org_id)
    
    # Get organization statistics
    farms = Farm.query.filter_by(organization_id=org.id).all()
    users = User.query.filter_by(organization_id=org.id).all()
    
    total_animals = db.session.query(func.count(Animal.id)).join(Farm).filter(
        Farm.organization_id == org.id,
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).scalar() or 0
    
    total_staff = db.session.query(func.count(func.distinct(StaffMembership.user_id))).join(Farm).filter(
        Farm.organization_id == org.id,
        StaffMembership.is_active == True
    ).scalar() or 0
    
    # Subscription history
    subscriptions = Subscription.query.filter_by(
        organization_id=org.id
    ).order_by(Subscription.created_at.desc()).all()
    
    # Usage vs limits
    usage = {
        'farms': len([f for f in farms if f.status == 'ACTIVE']),
        'animals': total_animals,
        'staff': total_staff,
    }
    
    limits = {
        'farms': org.max_farms,
        'animals': org.max_animals,
        'staff': org.max_staff,
    }
    
    return render_template('platform_admin/organization_detail.html',
                         organization=org,
                         farms=farms,
                         users=users,
                         subscriptions=subscriptions,
                         usage=usage,
                         limits=limits)


@platform_admin_bp.route('/organizations/<int:org_id>/suspend', methods=['POST'])
@login_required
@platform_admin_required
def suspend_organization(org_id):
    """Suspend an organization (make inactive)."""
    org = Organization.query.get_or_404(org_id)
    org.is_active = False
    org.subscription_status = 'SUSPENDED'
    org.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Organization "{org.name}" has been suspended.', 'success')
    return redirect(url_for('platform_admin.organization_detail', org_id=org.id))


@platform_admin_bp.route('/organizations/<int:org_id>/activate', methods=['POST'])
@login_required
@platform_admin_required
def activate_organization(org_id):
    """Reactivate a suspended organization."""
    org = Organization.query.get_or_404(org_id)
    org.is_active = True
    if org.subscription_status == 'SUSPENDED':
        org.subscription_status = 'ACTIVE'
    org.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Organization "{org.name}" has been activated.', 'success')
    return redirect(url_for('platform_admin.organization_detail', org_id=org.id))


@platform_admin_bp.route('/organizations/<int:org_id>/extend-trial', methods=['POST'])
@login_required
@platform_admin_required
def extend_trial(org_id):
    """Extend trial period for an organization."""
    org = Organization.query.get_or_404(org_id)
    days = request.form.get('days', 14, type=int)
    
    if org.trial_ends_at:
        org.trial_ends_at = org.trial_ends_at + timedelta(days=days)
    else:
        org.trial_ends_at = datetime.utcnow() + timedelta(days=days)
    
    org.subscription_status = 'TRIAL'
    org.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Trial extended by {days} days for "{org.name}".', 'success')
    return redirect(url_for('platform_admin.organization_detail', org_id=org.id))


@platform_admin_bp.route('/users')
@login_required
@platform_admin_required
def users():
    """List all users with filtering."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query.filter_by(is_platform_admin=False)
    
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%')
            )
        )
    
    # Paginate
    per_page = 50
    pagination = query.order_by(User.date_joined.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('platform_admin/users.html',
                         users=pagination.items,
                         pagination=pagination,
                         search=search)


@platform_admin_bp.route('/subscription-plans')
@login_required
@platform_admin_required
def subscription_plans():
    """Manage subscription plans."""
    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.sort_order).all()
    
    # Add subscriber count to each plan (use subscription_plan_id FK)
    for plan in plans:
        plan.subscriber_count = Organization.query.filter_by(subscription_plan_id=plan.id).count()
    
    return render_template('platform_admin/subscription_plans.html', plans=plans)


@platform_admin_bp.route('/subscription-plans/create', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def create_subscription_plan():
    """Create a new subscription plan."""
    from app.forms import SubscriptionPlanForm
    
    form = SubscriptionPlanForm()
    
    if form.validate_on_submit():
        plan = SubscriptionPlan(
            name=form.name.data,
            description=form.description.data,
            price_amount=form.price_amount.data,
            price_currency=form.price_currency.data,
            billing_period=form.billing_period.data,
            max_farms=form.max_farms.data,
            max_animals=form.max_animals.data,
            max_staff=form.max_staff.data,
            storage_limit_gb=form.storage_limit_gb.data,
            features=form.features.data,
            is_active=form.is_active.data,
            is_popular=form.is_popular.data,
            created_at=datetime.utcnow()
        )
        db.session.add(plan)
        db.session.commit()
        
        flash(f'Plan "{plan.name}" created successfully.', 'success')
        return redirect(url_for('platform_admin.subscription_plans'))
    
    return render_template('platform_admin/edit_subscription_plan.html', form=form, plan=None)


@platform_admin_bp.route('/subscription-plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def edit_subscription_plan(plan_id=None):
    """Edit a subscription plan."""
    from app.forms import SubscriptionPlanForm
    
    plan = SubscriptionPlan.query.get_or_404(plan_id) if plan_id else None
    if plan:
        plan.subscriber_count = Organization.query.filter_by(subscription_plan_id=plan.id).count()
    form = SubscriptionPlanForm(obj=plan)
    
    if form.validate_on_submit():
        if plan:
            plan.name = form.name.data
            plan.description = form.description.data
            plan.price_amount = form.price_amount.data
            plan.price_currency = form.price_currency.data
            plan.billing_period = form.billing_period.data
            plan.max_farms = form.max_farms.data
            plan.max_animals = form.max_animals.data
            plan.max_staff = form.max_staff.data
            plan.storage_limit_gb = form.storage_limit_gb.data
            plan.features = form.features.data
            plan.is_active = form.is_active.data
            plan.is_popular = form.is_popular.data
            plan.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Plan "{plan.name}" updated successfully.', 'success')
        
        return redirect(url_for('platform_admin.subscription_plans'))
    
    return render_template('platform_admin/edit_subscription_plan.html', form=form, plan=plan)


@platform_admin_bp.route('/analytics')
@login_required
@platform_admin_required
def analytics():
    """Platform analytics and reporting."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Signup trend (last 12 months) — labels + data for Chart.js
    revenue_labels, revenue_data, user_labels, user_data = [], [], [], []
    for i in range(11, -1, -1):
        month_start = (datetime.utcnow() - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (datetime.utcnow() - timedelta(days=30 * (i - 1))).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0) if i > 0 else datetime.utcnow()
        label = month_start.strftime('%b %Y')
        revenue_labels.append(label)
        user_labels.append(label)
        revenue_data.append(0)   # placeholder — real billing data would go here
        user_data.append(
            User.query.filter(
                User.date_joined >= month_start,
                User.date_joined < month_end,
                User.is_platform_admin == False
            ).count()
        )

    total_orgs = Organization.query.count()
    new_orgs = Organization.query.filter(Organization.created_at >= thirty_days_ago).count()
    active_users = User.query.filter_by(is_active=True, is_platform_admin=False).count()
    cancelled_last_30 = Organization.query.filter(
        Organization.subscription_status == 'CANCELLED',
        Organization.updated_at >= thirty_days_ago
    ).count()

    metrics = {
        'total_revenue': 0,
        'revenue_growth': 0,
        'new_organizations': new_orgs,
        'org_growth': 0,
        'active_users': active_users,
        'user_growth': 0,
        'churn_rate': round(cancelled_last_30 / max(total_orgs, 1) * 100, 1),
        'churn_trend': 0,
        'revenue_by_plan': [],
    }

    funnel = {
        'signups': total_orgs,
        'activated': Organization.query.filter(Organization.setup_completed == True).count(),
        'converted': Organization.query.filter_by(subscription_status='ACTIVE').count(),
        'retained': Organization.query.filter_by(subscription_status='ACTIVE').count(),
    }

    chart_data = {
        'revenue_labels': revenue_labels,
        'revenue_data': revenue_data,
        'user_labels': user_labels,
        'user_data': user_data,
    }

    # Top orgs by animal count
    top_orgs_query = db.session.query(
        Organization,
        func.count(Animal.id).label('animal_count'),
        func.count(func.distinct(User.id)).label('user_count'),
    ).outerjoin(Farm, Farm.organization_id == Organization.id
    ).outerjoin(Animal, Animal.farm_id == Farm.id
    ).outerjoin(User, User.organization_id == Organization.id
    ).group_by(Organization.id).order_by(desc('animal_count')).limit(10).all()

    top_organizations = [
        {'id': org.id, 'name': org.name, 'current_plan': org.current_plan or 'Trial',
         'animal_count': ac, 'user_count': uc}
        for org, ac, uc in top_orgs_query
    ]

    at_risk = Organization.query.filter(
        db.or_(
            db.and_(Organization.subscription_status == 'TRIAL',
                    Organization.trial_ends_at <= datetime.utcnow() + timedelta(days=7)),
            Organization.subscription_status == 'EXPIRED'
        )
    ).limit(10).all()

    return render_template('platform_admin/analytics.html',
                         metrics=metrics,
                         funnel=funnel,
                         chart_data=chart_data,
                         top_organizations=top_organizations,
                         at_risk_organizations=at_risk)


@platform_admin_bp.route('/system-health')
@login_required
@platform_admin_required
def system_health():
    """System health monitoring."""
    import time

    # Quick DB connectivity check
    t0 = time.time()
    db_ok = False
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception:
        pass
    db_response_ms = round((time.time() - t0) * 1000)

    db_health = {'status': 'healthy' if db_ok else 'error', 'response_time': db_response_ms}
    supabase_health = {'status': 'unknown', 'response_time': 0}
    redis_health = {'status': 'unknown', 'memory_usage': 0}
    celery_health = {'status': 'unknown', 'active_workers': 0}

    system_status = {
        'overall': 'healthy' if db_ok else 'degraded',
        'last_check': datetime.utcnow(),
        'uptime_days': 0,
        'uptime_percentage': 99.9,
    }

    neon_metrics = {
        'size_gb': 0,
        'usage_percentage': 0,
        'active_connections': 0,
        'max_connections': 100,
        'queries_per_second': 0,
        'avg_query_time': db_response_ms,
        'top_tables': [
            {'name': 'animals', 'size': str(Animal.query.count()) + ' rows'},
            {'name': 'organizations', 'size': str(Organization.query.count()) + ' rows'},
            {'name': 'users', 'size': str(User.query.count()) + ' rows'},
            {'name': 'farms', 'size': str(Farm.query.count()) + ' rows'},
        ]
    }

    supabase_metrics = {
        'size_gb': 0,
        'usage_percentage': 0,
        'archived_records': 0,
        'last_archival': None,
        'compression_ratio': 0,
        'oldest_record': 'N/A',
        'orgs_with_archives': 0,
    }

    performance = {
        'avg_response_time': db_response_ms,
        'requests_per_minute': 0,
        'error_rate': 0,
        'active_sessions': 0,
    }

    celery_stats = {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0}
    recent_jobs = []
    system_alerts = []

    # Real counts
    table_stats = {
        'organizations': Organization.query.count(),
        'users': User.query.count(),
        'farms': Farm.query.count(),
        'animals': Animal.query.count(),
        'subscriptions': Subscription.query.count(),
        'invitations': UserInvitation.query.count(),
    }

    expired_trials = Organization.query.filter(
        Organization.subscription_status == 'TRIAL',
        Organization.trial_ends_at < datetime.utcnow()
    ).count()

    if expired_trials > 0:
        system_alerts.append({
            'component': 'Subscriptions',
            'message': f'{expired_trials} trial(s) have expired without converting.',
            'severity': 'warning',
            'timestamp': datetime.utcnow(),
        })

    return render_template('platform_admin/system_health.html',
                         system_status=system_status,
                         db_health=db_health,
                         supabase_health=supabase_health,
                         redis_health=redis_health,
                         celery_health=celery_health,
                         neon_metrics=neon_metrics,
                         supabase_metrics=supabase_metrics,
                         performance=performance,
                         celery_stats=celery_stats,
                         recent_jobs=recent_jobs,
                         system_alerts=system_alerts,
                         table_stats=table_stats)
