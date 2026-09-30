import os
from flask import Flask
from flask_login import LoginManager
from config import config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.animals import animals_bp
    from app.routes.staff import staff_bp
    from app.routes.breeding import breeding_bp
    from app.routes.health import health_bp
    from app.routes.feed import feed_bp
    from app.routes.commercial import commercial_bp
    from app.routes.admin import admin_bp
    from app.routes.onboarding import onboarding_bp
    from app.routes.organization import organization_bp
    from app.routes.platform_admin import platform_admin_bp
    from app.routes.milking import milking_bp  # NEW: Milking module

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(animals_bp, url_prefix='/animals')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(breeding_bp, url_prefix='/breeding')
    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(feed_bp, url_prefix='/feed')
    app.register_blueprint(commercial_bp, url_prefix='/commercial')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(onboarding_bp, url_prefix='/onboarding')
    app.register_blueprint(organization_bp, url_prefix='/organization')
    app.register_blueprint(platform_admin_bp, url_prefix='/platform-admin')
    app.register_blueprint(milking_bp, url_prefix='/milking')  # NEW: Milking module

    # Context processors
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from flask import session
        farm_id = session.get('current_farm_id')
        current_farm = None
        user_role = None
        if current_user.is_authenticated and farm_id:
            from app.models import Farm
            current_farm = db.session.get(Farm, farm_id)
            if current_farm and current_user.has_farm_access(farm_id):
                user_role = current_user.get_role_for_farm(farm_id)
            else:
                session.pop('current_farm_id', None)
                current_farm = None
        return {
            'current_farm': current_farm,
            'user_role': user_role,
        }

    with app.app_context():
        db.create_all()
        _seed_initial_data()

    return app


def _seed_initial_data():
    """Seed roles, permissions, species, and subscription plans for SaaS.
    Short-circuits immediately if data already exists to avoid slow startup."""
    from app.models import Role

    # Fast check — if roles exist, everything is already seeded
    if Role.query.first():
        return

    from datetime import date, timedelta
    from app.models import (
        Role, Permission, RolePermission, Species, Breed,
        SubscriptionPlan
    )

    # Subscription Plans (SaaS pricing tiers)
    plans_data = [
        {
            'name': 'Trial',
            'slug': 'trial',
            'description': 'Free trial for 14 days - Try all features',
            'price_monthly': 0,
            'price_yearly': 0,
            'max_farms': 1,
            'max_animals': 50,
            'max_staff': 3,
            'max_storage_mb': 100,
            'trial_days': 14,
            'sort_order': 0,
            'features_json': {
                'animal_management': True,
                'health_records': True,
                'breeding_records': True,
                'feed_management': True,
                'basic_reports': True,
                'mobile_access': False,
                'api_access': False,
                'priority_support': False,
            }
        },
        {
            'name': 'Starter',
            'slug': 'starter',
            'description': 'Perfect for small farms',
            'price_monthly': 29,
            'price_yearly': 290,
            'max_farms': 1,
            'max_animals': 100,
            'max_staff': 5,
            'max_storage_mb': 500,
            'trial_days': 14,
            'sort_order': 1,
            'features_json': {
                'animal_management': True,
                'health_records': True,
                'breeding_records': True,
                'feed_management': True,
                'basic_reports': True,
                'sales_tracking': True,
                'expense_tracking': True,
                'mobile_access': True,
                'api_access': False,
                'priority_support': False,
            }
        },
        {
            'name': 'Professional',
            'slug': 'professional',
            'description': 'For growing farm businesses',
            'price_monthly': 79,
            'price_yearly': 790,
            'max_farms': 3,
            'max_animals': 500,
            'max_staff': 15,
            'max_storage_mb': 2000,
            'trial_days': 14,
            'sort_order': 2,
            'features_json': {
                'animal_management': True,
                'health_records': True,
                'breeding_records': True,
                'feed_management': True,
                'basic_reports': True,
                'advanced_reports': True,
                'sales_tracking': True,
                'expense_tracking': True,
                'inventory_management': True,
                'mobile_access': True,
                'api_access': True,
                'priority_support': True,
                'custom_fields': True,
            }
        },
        {
            'name': 'Enterprise',
            'slug': 'enterprise',
            'description': 'For large-scale operations',
            'price_monthly': 199,
            'price_yearly': 1990,
            'max_farms': 10,
            'max_animals': 2000,
            'max_staff': 50,
            'max_storage_mb': 10000,
            'trial_days': 14,
            'sort_order': 3,
            'features_json': {
                'animal_management': True,
                'health_records': True,
                'breeding_records': True,
                'feed_management': True,
                'basic_reports': True,
                'advanced_reports': True,
                'sales_tracking': True,
                'expense_tracking': True,
                'inventory_management': True,
                'mobile_access': True,
                'api_access': True,
                'priority_support': True,
                'custom_fields': True,
                'white_labeling': True,
                'dedicated_support': True,
                'custom_integrations': True,
            }
        },
    ]
    
    for plan_data in plans_data:
        existing = SubscriptionPlan.query.filter_by(slug=plan_data['slug']).first()
        if not existing:
            plan = SubscriptionPlan(**plan_data)
            db.session.add(plan)
    
    db.session.commit()

    # Roles
    roles_data = [
        ('OWNER', 'Owner', 'Full access to the farm'),
        ('ADMIN', 'Administrator', 'Administrative access'),
        ('FARM_STAFF', 'Farm Staff', 'Day-to-day operations'),
        ('VETERINARY', 'Veterinary', 'Health and treatment access'),
        ('INVENTORY_MANAGER', 'Inventory Manager', 'Feed and inventory management'),
        ('ACCOUNTANT', 'Accountant', 'Financial records access'),
    ]
    for code, name, desc in roles_data:
        if not Role.query.filter_by(code=code).first():
            db.session.add(Role(code=code, name=name, description=desc))
    db.session.commit()

    # Permissions
    perms = [
        ('view_dashboard', 'View Dashboard', 'dashboard'),
        ('manage_animals', 'Manage Animals', 'animals'),
        ('view_animals', 'View Animals', 'animals'),
        ('manage_breeding', 'Manage Breeding', 'breeding'),
        ('view_breeding', 'View Breeding', 'breeding'),
        ('manage_health', 'Manage Health', 'health'),
        ('view_health', 'View Health', 'health'),
        ('manage_feed', 'Manage Feed', 'feed'),
        ('view_feed', 'View Feed', 'feed'),
        ('manage_sales', 'Manage Sales', 'commercial'),
        ('view_sales', 'View Sales', 'commercial'),
        ('manage_expenses', 'Manage Expenses', 'commercial'),
        ('view_expenses', 'View Expenses', 'commercial'),
        ('manage_staff', 'Manage Staff', 'staff'),
        ('view_staff', 'View Staff', 'staff'),
        ('manage_locations', 'Manage Locations', 'locations'),
        ('manage_farm_settings', 'Manage Farm Settings', 'admin'),
        ('view_reports', 'View Reports', 'reports'),
        ('manage_permissions', 'Manage Permissions', 'admin'),
    ]
    for code, name, ct in perms:
        if not Permission.query.filter_by(codename=code).first():
            db.session.add(Permission(codename=code, name=name, content_type=ct))
    db.session.commit()

    # Assign all permissions to OWNER and ADMIN
    owner = Role.query.filter_by(code='OWNER').first()
    admin = Role.query.filter_by(code='ADMIN').first()
    all_perms = Permission.query.all()
    for role in (owner, admin):
        for p in all_perms:
            if not RolePermission.query.filter_by(role_id=role.id, permission_id=p.id).first():
                db.session.add(RolePermission(role_id=role.id, permission_id=p.id))

    # Farm staff limited
    staff_role = Role.query.filter_by(code='FARM_STAFF').first()
    staff_codes = ['view_dashboard', 'view_animals', 'manage_animals', 'view_breeding',
                   'view_health', 'manage_health', 'view_feed', 'view_sales', 'view_expenses']
    for code in staff_codes:
        p = Permission.query.filter_by(codename=code).first()
        if p and not RolePermission.query.filter_by(role_id=staff_role.id, permission_id=p.id).first():
            db.session.add(RolePermission(role_id=staff_role.id, permission_id=p.id))

    # Veterinary
    vet_role = Role.query.filter_by(code='VETERINARY').first()
    vet_codes = ['view_dashboard', 'view_animals', 'view_health', 'manage_health', 'view_breeding']
    for code in vet_codes:
        p = Permission.query.filter_by(codename=code).first()
        if p and not RolePermission.query.filter_by(role_id=vet_role.id, permission_id=p.id).first():
            db.session.add(RolePermission(role_id=vet_role.id, permission_id=p.id))

    # Inventory
    inv_role = Role.query.filter_by(code='INVENTORY_MANAGER').first()
    inv_codes = ['view_dashboard', 'view_feed', 'manage_feed', 'view_expenses']
    for code in inv_codes:
        p = Permission.query.filter_by(codename=code).first()
        if p and not RolePermission.query.filter_by(role_id=inv_role.id, permission_id=p.id).first():
            db.session.add(RolePermission(role_id=inv_role.id, permission_id=p.id))

    # Accountant
    acc_role = Role.query.filter_by(code='ACCOUNTANT').first()
    acc_codes = ['view_dashboard', 'view_sales', 'manage_sales', 'view_expenses', 'manage_expenses', 'view_reports']
    for code in acc_codes:
        p = Permission.query.filter_by(codename=code).first()
        if p and not RolePermission.query.filter_by(role_id=acc_role.id, permission_id=p.id).first():
            db.session.add(RolePermission(role_id=acc_role.id, permission_id=p.id))

    db.session.commit()

    # Species & Breeds
    if not Species.query.first():
        goat = Species(name='Goat')
        sheep = Species(name='Sheep')
        cattle = Species(name='Cattle')
        db.session.add_all([goat, sheep, cattle])
        db.session.commit()
        db.session.add_all([
            Breed(species_id=goat.id, name='Boer'),
            Breed(species_id=goat.id, name='Saanen'),
            Breed(species_id=goat.id, name='Jamunapari'),
            Breed(species_id=goat.id, name='Black Bengal'),
            Breed(species_id=sheep.id, name='Merino'),
            Breed(species_id=sheep.id, name='Dorper'),
            Breed(species_id=cattle.id, name='Holstein'),
            Breed(species_id=cattle.id, name='Jersey'),
            Breed(species_id=cattle.id, name='Sahiwal'),
        ])
        db.session.commit()
    
    # Create a platform admin user (for system administration)
    # In production, this should be created via a secure setup script
    admin_user = User.query.filter_by(username='platformadmin').first()
    if not admin_user:
        admin_user = User(
            username='platformadmin',
            email='admin@farmit.platform',
            first_name='Platform',
            last_name='Administrator',
            is_active=True,
            is_platform_admin=True,
            is_organization_owner=False,
        )
        admin_user.set_password('ChangeMeInProduction123!')
        db.session.add(admin_user)
        db.session.commit()
        print('⚠️  Platform admin created: username=platformadmin, password=ChangeMeInProduction123!')
        print('⚠️  Please change the password immediately!')
