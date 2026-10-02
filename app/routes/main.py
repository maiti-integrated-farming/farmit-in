from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user
from app.models import db, Farm, Animal, Vaccination, Deworming, Treatment, Notification, Expense, AnimalSale, Feed
from app.decorators import farm_required, organization_required
from datetime import date, timedelta
from sqlalchemy import func

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.select_farm'))
    return redirect(url_for('auth.login'))


@main_bp.route('/no-access')
@login_required
def no_access():
    """Page for users without farm access."""
    return render_template('main/no_access.html')


@main_bp.route('/select-farm', methods=['GET', 'POST'])
@login_required
@organization_required
def select_farm():
    """Select a farm to work with - with tenant isolation."""
    # Platform admins can see all farms (for support purposes)
    if current_user.is_platform_admin:
        memberships = []
        # In admin mode, they need to select an organization first (not implemented in this phase)
        farms = Farm.query.filter_by(status='ACTIVE').limit(50).all()
    else:
        memberships = current_user.get_memberships(active_only=True)
        # Get all farms in the user's organization that they have access to
        farms = [m.farm for m in memberships if m.farm and m.farm.status == 'ACTIVE']
    
    if not farms and not current_user.is_platform_admin:
        flash('You are not assigned to any farm. Contact your organization owner.', 'warning')
        return render_template('main/select_farm.html', memberships=[], farms=[])

    if request.method == 'POST':
        farm_id = request.form.get('farm_id', type=int)
        
        # Verify farm access and tenant isolation
        if current_user.is_platform_admin:
            farm = db.session.get(Farm, farm_id)
            if farm:
                session['current_farm_id'] = farm_id
                flash('Farm selected successfully (Admin Mode).', 'success')
                return redirect(url_for('main.dashboard'))
        elif farm_id and current_user.has_farm_access(farm_id):
            # Double-check tenant isolation
            farm = db.session.get(Farm, farm_id)
            if farm and farm.organization_id == current_user.organization_id:
                session['current_farm_id'] = farm_id
                flash('Farm selected successfully.', 'success')
                return redirect(url_for('main.dashboard'))
            else:
                flash('Access denied: Farm does not belong to your organization.', 'danger')
        else:
            flash('Invalid farm selection.', 'danger')

    # Auto-select if only one farm
    if len(farms) == 1 and not session.get('current_farm_id'):
        session['current_farm_id'] = farms[0].id
        return redirect(url_for('main.dashboard'))

    return render_template('main/select_farm.html', memberships=memberships, farms=farms)


@main_bp.route('/dashboard')
@login_required
@farm_required
def dashboard():
    """Farm dashboard with tenant-isolated data."""
    from app.models import FeedAlert, Feed
    
    farm_id = session['current_farm_id']
    farm = db.session.get(Farm, farm_id)
    
    # Verify tenant isolation - farm must belong to user's organization
    if not current_user.is_platform_admin:
        if not farm or farm.organization_id != current_user.organization_id:
            flash('Access denied to this farm.', 'danger')
            session.pop('current_farm_id', None)
            return redirect(url_for('main.select_farm'))

    # Stats - all queries are automatically scoped to farm_id
    total_animals = Animal.query.filter_by(farm_id=farm_id).filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).count()
    male_count = Animal.query.filter_by(farm_id=farm_id, gender='MALE').filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).count()
    female_count = Animal.query.filter_by(farm_id=farm_id, gender='FEMALE').filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).count()
    sick_count = Animal.query.filter_by(farm_id=farm_id, status='SICK').count()

    today = date.today()
    upcoming_vacc = Vaccination.query.filter(
        Vaccination.farm_id == farm_id,
        Vaccination.next_due_date <= today + timedelta(days=14),
        Vaccination.next_due_date >= today
    ).count()
    upcoming_dew = Deworming.query.filter(
        Deworming.farm_id == farm_id,
        Deworming.next_due_date <= today + timedelta(days=14),
        Deworming.next_due_date >= today
    ).count()

    # Recent expenses (last 30 days)
    month_ago = today - timedelta(days=30)
    recent_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.farm_id == farm_id,
        Expense.expense_date >= month_ago
    ).scalar() or 0

    recent_sales = db.session.query(func.coalesce(func.sum(AnimalSale.total_amount), 0)).filter(
        AnimalSale.farm_id == farm_id,
        AnimalSale.sale_date >= month_ago
    ).scalar() or 0

    low_stock = Feed.query.filter(
        Feed.farm_id == farm_id,
        Feed.stock_quantity <= Feed.minimum_stock
    ).count()

    recent_animals = Animal.query.filter_by(farm_id=farm_id).order_by(
        Animal.created_at.desc()
    ).limit(5).all()

    unread_notifs = Notification.query.filter_by(
        farm_id=farm_id, recipient_id=current_user.id, is_read=False
    ).count()
    
    # NEW: Calculate total daily feed requirement
    active_animals = Animal.query.filter_by(farm_id=farm_id).filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'LACTATING', 'MILKING', 'GROWING'])
    ).all()
    
    total_daily_feed = sum(animal.calculate_daily_feed_requirement() for animal in active_animals)
    
    # NEW: Get current feed stock total
    total_feed_stock = db.session.query(func.coalesce(func.sum(Feed.stock_quantity), 0)).filter(
        Feed.farm_id == farm_id
    ).scalar() or 0
    
    # NEW: Calculate days of feed remaining
    days_feed_remaining = int(total_feed_stock / total_daily_feed) if total_daily_feed > 0 else 0
    
    # NEW: Get unresolved feed alerts
    feed_alerts = FeedAlert.query.filter_by(
        farm_id=farm_id,
        is_resolved=False
    ).order_by(FeedAlert.severity.desc()).limit(5).all()
    low_stock_feeds = Feed.query.filter(
        Feed.farm_id == farm_id,
        Feed.stock_quantity <= Feed.minimum_stock
    ).order_by(Feed.stock_quantity.asc()).all()
    
    # NEW: Determine feed alert level
    feed_alert_level = 'success'  # Green
    if days_feed_remaining < 3:
        feed_alert_level = 'danger'  # Red
    elif days_feed_remaining < 7:
        feed_alert_level = 'warning'  # Yellow

    stats = {
        'total_animals': total_animals,
        'male_count': male_count,
        'female_count': female_count,
        'sick_count': sick_count,
        'upcoming_vacc': upcoming_vacc,
        'upcoming_dew': upcoming_dew,
        'recent_expenses': float(recent_expenses),
        'recent_sales': float(recent_sales),
        'low_stock': low_stock,
        'unread_notifs': unread_notifs,
        # NEW feed stats
        'total_daily_feed': round(total_daily_feed, 2),
        'total_feed_stock': float(total_feed_stock),
        'days_feed_remaining': days_feed_remaining,
        'feed_alerts_count': len(feed_alerts),
        'feed_alert_level': feed_alert_level,
        'low_stock_feed_count': len(low_stock_feeds),
    }

    return render_template('main/dashboard.html', 
                         farm=farm, 
                         stats=stats, 
                         recent_animals=recent_animals,
                         feed_alerts=feed_alerts,
                         low_stock_feeds=low_stock_feeds)


@main_bp.route('/switch-farm/<int:farm_id>')
@login_required
@organization_required
def switch_farm(farm_id):
    """Switch to a different farm with tenant isolation check."""
    # Verify farm belongs to user's organization
    farm = db.session.get(Farm, farm_id)
    
    if current_user.is_platform_admin:
        if farm:
            session['current_farm_id'] = farm_id
            flash('Switched farm successfully (Admin Mode).', 'success')
        else:
            flash('Farm not found.', 'danger')
    elif farm and farm.organization_id == current_user.organization_id and current_user.has_farm_access(farm_id):
        session['current_farm_id'] = farm_id
        flash('Switched farm successfully.', 'success')
    else:
        flash('Access denied: Farm does not belong to your organization.', 'danger')
    
    return redirect(url_for('main.dashboard'))
