from datetime import datetime, date
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index, UniqueConstraint, func

db = SQLAlchemy()
MAX_FARMS_PER_ORGANIZATION = 5


# ---------------------------------------------------------------------------
# TENANT / ACCESS
# ---------------------------------------------------------------------------

class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(60), nullable=False, unique=True)
    description = db.Column(db.Text)

    # Pricing — price_amount/price_currency/billing_period used by routes & templates
    price_amount = db.Column(db.Numeric(10, 2), default=0)       # canonical price field
    price_currency = db.Column(db.String(3), default='USD')       # e.g. USD, EUR
    billing_period = db.Column(db.String(10), default='month')    # 'month' or 'year'
    # Keep legacy columns for backwards compat with seed data
    price_monthly = db.Column(db.Numeric(10, 2), default=0)
    price_yearly = db.Column(db.Numeric(10, 2), default=0)
    currency = db.Column(db.String(3), default='USD')

    # Limits
    max_farms = db.Column(db.Integer, default=1)
    max_animals = db.Column(db.Integer, default=50)
    max_staff = db.Column(db.Integer, default=3)
    max_storage_mb = db.Column(db.Integer, default=500)
    storage_limit_gb = db.Column(db.Integer, default=1)           # storage in GB for display

    # Features
    features_json = db.Column(db.JSON)                            # feature flags as JSON dict
    features = db.Column(db.Text)                                  # comma-separated feature list for display

    # Marketing / status
    is_active = db.Column(db.Boolean, default=True)
    is_popular = db.Column(db.Boolean, default=False)
    trial_days = db.Column(db.Integer, default=14)
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizations = db.relationship('Organization', backref='plan', lazy='dynamic')

    def __repr__(self):
        return f'<SubscriptionPlan {self.name}>'


class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False)
    
    # Billing cycle
    billing_cycle = db.Column(db.String(20))  # MONTHLY, YEARLY
    amount = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(3), default='USD')
    
    # Dates
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    
    # Payment tracking
    status = db.Column(db.String(20), default='PENDING')  # PENDING, ACTIVE, EXPIRED, CANCELLED
    payment_method = db.Column(db.String(40))  # CARD, BANK_TRANSFER, PAYPAL, etc.
    payment_reference = db.Column(db.String(120))
    last_payment_date = db.Column(db.DateTime)
    next_payment_date = db.Column(db.DateTime)
    
    # Auto-renewal
    auto_renew = db.Column(db.Boolean, default=True)
    cancelled_at = db.Column(db.DateTime)
    cancellation_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    plan = db.relationship('SubscriptionPlan', backref='subscriptions')
    
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status == 'ACTIVE' and datetime.utcnow() < self.ends_at
    
    def __repr__(self):
        return f'<Subscription org={self.organization_id} plan={self.plan_id}>'


class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Contact and business info
    business_email = db.Column(db.String(120))
    contact_email = db.Column(db.String(120))   # alias used by profile form/routes
    phone = db.Column(db.String(30))
    contact_phone = db.Column(db.String(30))    # alias used by profile form/routes
    address = db.Column(db.Text)
    country = db.Column(db.String(60))
    timezone = db.Column(db.String(60), default='UTC')

    # Subscription and billing
    subscription_plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'))
    current_plan = db.Column(db.String(80))                  # plan name string for quick display
    subscription_status = db.Column(db.String(20), default='TRIAL')
    trial_ends_at = db.Column(db.DateTime)
    subscription_starts_at = db.Column(db.DateTime)
    subscription_ends_at = db.Column(db.DateTime)
    # Aliases used by routes (subscription_start_date / subscription_end_date)
    subscription_start_date = db.Column(db.DateTime)
    subscription_end_date = db.Column(db.DateTime)
    auto_renew = db.Column(db.Boolean, default=True)

    # Limits
    max_farms = db.Column(db.Integer, default=1)
    max_animals = db.Column(db.Integer, default=50)
    max_staff = db.Column(db.Integer, default=3)
    storage_limit_gb = db.Column(db.Integer, default=1)
    
    # Status and metadata
    is_active = db.Column(db.Boolean, default=True)
    setup_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_organization')
    farms = db.relationship('Farm', backref='organization', lazy='dynamic')
    subscriptions = db.relationship('Subscription', backref='organization', lazy='dynamic')

    @property
    def users(self):
        """Alias for 'members' backref — templates use organization.users."""
        return self.members

    def is_subscription_active(self):
        """Check if organization has an active subscription or trial."""
        if self.subscription_status in ['ACTIVE', 'TRIAL']:
            if self.subscription_status == 'TRIAL' and self.trial_ends_at:
                return datetime.utcnow() < self.trial_ends_at
            elif self.subscription_status == 'ACTIVE' and self.subscription_ends_at:
                return datetime.utcnow() < self.subscription_ends_at
            return True
        return False
    
    def can_add_farm(self):
        """Check the platform-wide farm creation limit for this organization."""
        return self.farms.count() < MAX_FARMS_PER_ORGANIZATION

    @property
    def farm_limit(self):
        return MAX_FARMS_PER_ORGANIZATION
    
    def can_add_animal(self):
        """Check if organization can add more animals."""
        from sqlalchemy import func
        total_animals = db.session.query(func.count(Animal.id)).join(Farm).filter(
            Farm.organization_id == self.id,
            Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
        ).scalar() or 0
        return total_animals < self.max_animals
    
    def can_add_staff(self, user_id=None):
        """Check the unique staff limit, without charging for additional farm assignments."""
        if user_id is not None:
            existing_staff = db.session.query(StaffMembership.id).join(Farm).filter(
                Farm.organization_id == self.id,
                StaffMembership.user_id == user_id,
                StaffMembership.is_active == True,
            ).first()
            if existing_staff:
                return True

        total_staff = db.session.query(func.count(func.distinct(StaffMembership.user_id))).join(Farm).filter(
            Farm.organization_id == self.id,
            StaffMembership.is_active == True,
            StaffMembership.user_id != self.owner_id,
        ).scalar() or 0
        return total_staff < self.max_staff

    def __repr__(self):
        return f'<Organization {self.name}>'


class Farm(db.Model):
    __tablename__ = 'farms'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(40), unique=True, nullable=False)
    address = db.Column(db.Text)
    contact_phone = db.Column(db.String(30))
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, INACTIVE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    locations = db.relationship('Location', backref='farm', lazy='dynamic')
    staff_memberships = db.relationship('StaffMembership', backref='farm', lazy='dynamic')
    animals = db.relationship('Animal', backref='farm', lazy='dynamic')

    def __repr__(self):
        return f'<Farm {self.name}>'


class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    animals = db.relationship('Animal', backref='location', lazy='dynamic')

    def __repr__(self):
        return f'<Location {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(30))
    photo = db.Column(db.String(255))
    
    # Organization membership - every user belongs to one organization
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    
    # User status and roles
    is_active = db.Column(db.Boolean, default=True)
    is_platform_admin = db.Column(db.Boolean, default=False)
    is_organization_owner = db.Column(db.Boolean, default=False)
    is_organization_admin = db.Column(db.Boolean, default=False)  # org-level admin (not owner)
    
    # Invitation tracking
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    invitation_token = db.Column(db.String(100), unique=True)
    invitation_accepted_at = db.Column(db.DateTime)
    
    # Timestamps
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    organization = db.relationship('Organization', foreign_keys=[organization_id], backref='members')
    memberships = db.relationship('StaffMembership', backref='user', lazy='dynamic')
    inviter = db.relationship('User', remote_side=[id], backref='invited_users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f'{self.first_name or ""} {self.last_name or ""}'.strip() or self.username

    def get_memberships(self, active_only=True):
        """Get all farm memberships for this user within their organization."""
        q = self.memberships
        if active_only:
            q = q.filter_by(is_active=True)
        return q.all()

    def has_farm_access(self, farm_id):
        """Check if user has access to a specific farm."""
        if self.is_platform_admin:
            return True
        # Check if farm belongs to user's organization
        farm = db.session.get(Farm, farm_id)
        if not farm or farm.organization_id != self.organization_id:
            return False
        # Check if user has membership in this farm
        return self.memberships.filter_by(farm_id=farm_id, is_active=True).first() is not None

    def has_organization_access(self, organization_id):
        """Check if user belongs to the organization."""
        if self.is_platform_admin:
            return True
        return self.organization_id == organization_id

    def get_role_for_farm(self, farm_id):
        """Get user's role for a specific farm."""
        m = self.memberships.filter_by(farm_id=farm_id, is_active=True).first()
        return m.role if m else None

    def has_permission(self, farm_id, codename):
        """Check if user has a specific permission for a farm."""
        if self.is_platform_admin:
            return True
        if self.is_organization_owner:
            # Organization owners have all permissions
            farm = db.session.get(Farm, farm_id)
            if farm and farm.organization_id == self.organization_id:
                return True
        role = self.get_role_for_farm(farm_id)
        if not role:
            return False
        return any(p.codename == codename for p in role.permissions)
    
    def is_owner_of_organization(self):
        """Check if user is the owner of their organization."""
        if not self.organization_id:
            return False
        org = db.session.get(Organization, self.organization_id)
        return org and org.owner_id == self.id

    def __repr__(self):
        return f'<User {self.username}>'


class UserInvitation(db.Model):
    __tablename__ = 'user_invitations'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    
    # Invitation details
    invited_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_code = db.Column(db.String(40))  # Suggested role for the user
    farm_ids = db.Column(db.JSON)  # List of farm IDs they'll have access to
    
    # Status
    status = db.Column(db.String(20), default='PENDING')  # PENDING, ACCEPTED, EXPIRED, CANCELLED
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    inviter = db.relationship('User', foreign_keys=[invited_by], backref='sent_invitations')
    acceptor = db.relationship('User', foreign_keys=[accepted_by_user_id])
    
    def is_valid(self):
        """Check if invitation is still valid."""
        return self.status == 'PENDING' and datetime.utcnow() < self.expires_at
    
    def __repr__(self):
        return f'<UserInvitation {self.email}>'


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = db.relationship('Permission', secondary='role_permissions', backref='roles')
    memberships = db.relationship('StaffMembership', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.code}>'


class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    codename = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    content_type = db.Column(db.String(60))  # module

    def __repr__(self):
        return f'<Permission {self.codename}>'


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)

    __table_args__ = (UniqueConstraint('role_id', 'permission_id', name='uq_role_perm'),)


class StaffMembership(db.Model):
    __tablename__ = 'staff_memberships'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    staff_code = db.Column(db.String(40))
    designation = db.Column(db.String(80))
    joining_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    deactivated_at = db.Column(db.DateTime)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint('user_id', 'farm_id', name='uq_user_farm'),)

    def __repr__(self):
        return f'<StaffMembership user={self.user_id} farm={self.farm_id}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(20))  # CREATE, UPDATE, DELETE, OTHER
    module = db.Column(db.String(60))
    record_repr = db.Column(db.String(255))
    record_id = db.Column(db.String(60))
    old_value = db.Column(db.JSON)
    new_value = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))


# ---------------------------------------------------------------------------
# ANIMAL
# ---------------------------------------------------------------------------

class Species(db.Model):
    __tablename__ = 'species'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    breeds = db.relationship('Breed', backref='species', lazy='dynamic')

    def __repr__(self):
        return f'<Species {self.name}>'


class Breed(db.Model):
    __tablename__ = 'breeds'
    id = db.Column(db.Integer, primary_key=True)
    species_id = db.Column(db.Integer, db.ForeignKey('species.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    animals = db.relationship('Animal', backref='breed', lazy='dynamic')

    def __repr__(self):
        return f'<Breed {self.name}>'


class Animal(db.Model):
    __tablename__ = 'animals'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    tag_no = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(80))
    gender = db.Column(db.String(10))  # MALE, FEMALE
    breed_id = db.Column(db.Integer, db.ForeignKey('breeds.id'), nullable=False)
    date_of_birth = db.Column(db.Date)
    mother_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    father_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    color = db.Column(db.String(60))
    birth_weight = db.Column(db.Numeric(10, 2))
    current_weight = db.Column(db.Numeric(10, 2))
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Numeric(12, 2))
    feed_id = db.Column(db.Integer, db.ForeignKey('feeds.id'))
    daily_feed_quantity = db.Column(db.Numeric(12, 2))
    source = db.Column(db.String(30))  # BORN_ON_FARM, PURCHASED
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, PREGNANT, SICK, QUARANTINE, SOLD, DEAD, CULLED
    photo = db.Column(db.String(255))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    mother = db.relationship('Animal', remote_side=[id], foreign_keys=[mother_id], backref='offspring_as_mother')
    father = db.relationship('Animal', remote_side=[id], foreign_keys=[father_id], backref='offspring_as_father')
    assigned_feed = db.relationship('Feed', backref='assigned_animals')

    __table_args__ = (
        UniqueConstraint('farm_id', 'tag_no', name='unique_tag_no_per_farm'),
        Index('ix_animals_farm_status', 'farm_id', 'status'),
        Index('ix_animals_farm_gender', 'farm_id', 'gender'),
    )
    
    def calculate_daily_feed_requirement(self):
        """
        Calculate daily feed requirement based on weight, age, and status.
        Returns amount in kg.
        """
        if self.daily_feed_quantity is not None:
            return float(self.daily_feed_quantity)
        if not self.current_weight:
            return 0.0
        
        # Base requirement: 3% of body weight for maintenance
        base_requirement = float(self.current_weight) * 0.03
        
        # Adjust based on status
        if self.status == 'PREGNANT':
            base_requirement *= 1.2  # 20% more for pregnant animals
        elif self.status in ['LACTATING', 'MILKING']:
            base_requirement *= 1.5  # 50% more for lactating animals
        elif self.status == 'GROWING':
            base_requirement *= 1.3  # 30% more for growing animals
        elif self.status == 'SICK':
            base_requirement *= 0.8  # 20% less for sick animals
        
        return round(base_requirement, 2)
    
    def get_age_in_months(self):
        """Calculate age in months."""
        if not self.date_of_birth:
            return None
        today = date.today()
        return (today.year - self.date_of_birth.year) * 12 + (today.month - self.date_of_birth.month)
    
    def get_age_in_days(self):
        """Calculate age in days."""
        if not self.date_of_birth:
            return None
        return (date.today() - self.date_of_birth).days
    
    def is_lactating(self):
        """Check if animal is currently lactating/milking."""
        # Check if there are recent milking records (within last 7 days)
        if not hasattr(self, 'milking_records'):
            return False
        from datetime import timedelta
        seven_days_ago = date.today() - timedelta(days=7)
        recent_milking = any(record.date >= seven_days_ago for record in self.milking_records)
        return recent_milking or self.status in ['LACTATING', 'MILKING']

    def __repr__(self):
        return f'<Animal {self.tag_no}>'


class AnimalMovement(db.Model):
    __tablename__ = 'animal_movements'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    from_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    to_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    movement_date = db.Column(db.Date)
    reason = db.Column(db.String(120))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='movements')
    from_location = db.relationship('Location', foreign_keys=[from_location_id])
    to_location = db.relationship('Location', foreign_keys=[to_location_id])


class AnimalWeight(db.Model):
    __tablename__ = 'animal_weights'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    weight_date = db.Column(db.Date)
    weight_kg = db.Column(db.Numeric(10, 2))
    weight_method = db.Column(db.String(20))  # SCALE, TAPE, ESTIMATED
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='weights')


# ---------------------------------------------------------------------------
# BREEDING
# ---------------------------------------------------------------------------

class BreedingRecord(db.Model):
    __tablename__ = 'breeding_records'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    female_animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    male_animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    heat_date = db.Column(db.Date)
    mating_date = db.Column(db.Date)
    mating_method = db.Column(db.String(20))  # NATURAL, AI
    expected_delivery_date = db.Column(db.Date)
    pregnancy_status = db.Column(db.String(20), default='UNKNOWN')  # UNKNOWN, CONFIRMED, NOT_PREGNANT, DELIVERED, ABORTED
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    female = db.relationship('Animal', foreign_keys=[female_animal_id], backref='breeding_as_female')
    male = db.relationship('Animal', foreign_keys=[male_animal_id], backref='breeding_as_male')
    kidding_records = db.relationship('KiddingRecord', backref='breeding_record', lazy='dynamic')

    __table_args__ = (Index('ix_breeding_farm_status', 'farm_id', 'pregnancy_status'),)


class KiddingRecord(db.Model):
    __tablename__ = 'kidding_records'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    breeding_record_id = db.Column(db.Integer, db.ForeignKey('breeding_records.id'))
    female_animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    kidding_date = db.Column(db.Date)
    number_of_kids = db.Column(db.Integer)
    male_kids = db.Column(db.Integer)
    female_kids = db.Column(db.Integer)
    birth_assistance = db.Column(db.String(30))  # NONE, ASSISTED, VET_ASSISTED
    complication = db.Column(db.String(120))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    female = db.relationship('Animal', foreign_keys=[female_animal_id])
    kids = db.relationship('Kid', backref='kidding_record', lazy='dynamic')


class Kid(db.Model):
    __tablename__ = 'kids'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    kidding_record_id = db.Column(db.Integer, db.ForeignKey('kidding_records.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), unique=True)
    tag_no = db.Column(db.String(40))
    gender = db.Column(db.String(10))
    birth_weight = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='kid_record')


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

class Vaccination(db.Model):
    __tablename__ = 'vaccinations'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    vaccine = db.Column(db.String(120))
    date = db.Column(db.Date)
    dose = db.Column(db.String(40))
    batch_no = db.Column(db.String(60))
    next_due_date = db.Column(db.Date)
    cost = db.Column(db.Numeric(12, 2))
    administered_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='vaccinations')
    admin_user = db.relationship('User', foreign_keys=[administered_by])

    __table_args__ = (Index('ix_vacc_farm_due', 'farm_id', 'next_due_date'),)


class Deworming(db.Model):
    __tablename__ = 'dewormings'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    medicine = db.Column(db.String(120))
    date = db.Column(db.Date)
    dose = db.Column(db.String(40))
    body_weight = db.Column(db.Numeric(10, 2))
    next_due_date = db.Column(db.Date)
    administered_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='dewormings')
    admin_user = db.relationship('User', foreign_keys=[administered_by])

    __table_args__ = (Index('ix_dew_farm_due', 'farm_id', 'next_due_date'),)


class Treatment(db.Model):
    __tablename__ = 'treatments'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    
    # Category support
    category_id = db.Column(db.Integer, db.ForeignKey('treatment_categories.id'))
    treatment_type = db.Column(db.String(50))  # GENERAL, DEWORMING, CALCIUM_VITAMIN, VACCINATION, OTHER
    
    # Basic info
    date = db.Column(db.Date)
    symptoms = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    
    # Medication details
    medicine = db.Column(db.String(120))
    medication_template_id = db.Column(db.Integer, db.ForeignKey('medication_templates.id'))
    dose = db.Column(db.String(40))
    dosage_unit = db.Column(db.String(20))
    administration_route = db.Column(db.String(50))  # ORAL, INJECTION, TOPICAL, IV
    
    # Schedule
    frequency = db.Column(db.String(100))  # Once, Daily, Twice daily, Weekly
    duration_days = db.Column(db.Integer)
    next_dose_date = db.Column(db.Date)
    
    # Personnel
    vet = db.Column(db.Integer, db.ForeignKey('users.id'))
    follow_up_date = db.Column(db.Date)
    
    # Cost
    cost = db.Column(db.Numeric(10, 2))
    
    # Notes
    remarks = db.Column(db.Text)
    
    # Status
    is_completed = db.Column(db.Boolean, default=False)
    completion_date = db.Column(db.Date)
    
    # Withdrawal period (for food animals)
    withdrawal_period_days = db.Column(db.Integer)
    withdrawal_end_date = db.Column(db.Date)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='treatments')
    vet_user = db.relationship('User', foreign_keys=[vet])
    category = db.relationship('TreatmentCategory', backref='treatments')
    medication_template = db.relationship('MedicationTemplate', backref='treatments')

    __table_args__ = (Index('ix_treat_farm_followup', 'farm_id', 'follow_up_date'),)


# ---------------------------------------------------------------------------
# FEED
# ---------------------------------------------------------------------------

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    feeds = db.relationship('Feed', backref='supplier', lazy='dynamic')
    purchases = db.relationship('Purchase', backref='supplier', lazy='dynamic')


class Feed(db.Model):
    __tablename__ = 'feeds'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    feed_name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20))  # KG, BAG, LITRE
    purchase_price = db.Column(db.Numeric(12, 2))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    stock_quantity = db.Column(db.Numeric(12, 2), default=0)
    minimum_stock = db.Column(db.Numeric(12, 2), default=0)
    expiry_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    consumptions = db.relationship('FeedConsumption', backref='feed', lazy='dynamic')

    __table_args__ = (UniqueConstraint('farm_id', 'feed_name', name='uq_farm_feed_name'),)


class FeedConsumption(db.Model):
    __tablename__ = 'feed_consumptions'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    feed_id = db.Column(db.Integer, db.ForeignKey('feeds.id'), nullable=False)
    date = db.Column(db.Date)
    quantity = db.Column(db.Numeric(12, 2))
    animal_category = db.Column(db.String(20))  # ALL, KIDS, FEMALE, MALE
    number_of_animals = db.Column(db.Integer)
    cost = db.Column(db.Numeric(12, 2))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))


# ---------------------------------------------------------------------------
# COMMERCIAL
# ---------------------------------------------------------------------------

class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    purchase_date = db.Column(db.Date)
    item_type = db.Column(db.String(30))  # FEED, MEDICINE, EQUIPMENT, OTHER
    item_name = db.Column(db.String(120))
    quantity = db.Column(db.Numeric(12, 2))
    unit_price = db.Column(db.Numeric(12, 2))
    total_amount = db.Column(db.Numeric(14, 2))
    payment_status = db.Column(db.String(20))  # PAID, PARTIAL, UNPAID
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    sales = db.relationship('AnimalSale', backref='buyer', lazy='dynamic')


class AnimalSale(db.Model):
    __tablename__ = 'animal_sales'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), unique=True, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    sale_date = db.Column(db.Date)
    live_weight = db.Column(db.Numeric(10, 2))
    rate_per_kg = db.Column(db.Numeric(10, 2))
    total_amount = db.Column(db.Numeric(14, 2))
    payment_mode = db.Column(db.String(30))  # CASH, BANK_TRANSFER, UPI, OTHER
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref=db.backref('sale', uselist=False))


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    expense_date = db.Column(db.Date)
    category = db.Column(db.String(40))  # FEED, MEDICINE, VACCINE, ANIMAL_PURCHASE, LABOUR, ELECTRICITY, TRANSPORT, REPAIR, OTHER
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(14, 2))
    payment_mode = db.Column(db.String(30))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    __table_args__ = (Index('ix_expense_farm_cat_date', 'farm_id', 'category', 'expense_date'),)


class MilkRecord(db.Model):
    __tablename__ = 'milk_records'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    milking_date = db.Column(db.Date)
    milking_time = db.Column(db.Time)
    session = db.Column(db.String(20))  # MORNING, EVENING
    quantity_liters = db.Column(db.Numeric(10, 2))
    density = db.Column(db.Numeric(6, 3))
    fat_percentage = db.Column(db.Numeric(5, 2))
    snf_percentage = db.Column(db.Numeric(5, 2))
    protein_percentage = db.Column(db.Numeric(5, 2))
    temperature = db.Column(db.Numeric(5, 2))
    quality_status = db.Column(db.String(20))
    measurement_method = db.Column(db.String(40))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    animal = db.relationship('Animal', backref='milk_records')


# ---------------------------------------------------------------------------
# SYSTEM
# ---------------------------------------------------------------------------

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type = db.Column(db.String(40))  # VACCINATION_DUE, DEWORMING_DUE, ...
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='notifications')


class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    file_url = db.Column(db.String(500))
    file_type = db.Column(db.String(30))  # PHOTO, VET_DOCUMENT, BILL, INVOICE, ARCHIVE, OTHER
    related_module = db.Column(db.String(60))
    related_record_id = db.Column(db.String(60))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# MILKING MODULE - Complete milk production tracking
# ---------------------------------------------------------------------------

class MilkingRecord(db.Model):
    """Daily milking records per animal with session-based tracking."""
    __tablename__ = 'milking_records'
    
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    
    # Date and session
    date = db.Column(db.Date, nullable=False, index=True)
    session = db.Column(db.String(20), default='MORNING')  # MORNING, AFTERNOON, EVENING
    
    # Quantity (in liters)
    quantity = db.Column(db.Float, default=0.0)
    
    # Quality metrics
    fat_content = db.Column(db.Float)  # percentage
    protein_content = db.Column(db.Float)  # percentage
    lactose_content = db.Column(db.Float)  # percentage
    snf = db.Column(db.Float)  # Solids Not Fat percentage
    density = db.Column(db.Float)  # g/ml
    temperature = db.Column(db.Float)  # Celsius
    
    # Quality grade
    quality_grade = db.Column(db.String(5))  # A, A+, B, C, REJECT
    
    # Commercial
    price_per_liter = db.Column(db.Numeric(10, 2))
    total_amount = db.Column(db.Numeric(10, 2))
    
    # Notes
    notes = db.Column(db.Text)
    anomalies = db.Column(db.Text)  # Blood in milk, unusual color, etc.
    
    # Status
    is_sold = db.Column(db.Boolean, default=False)
    sale_reference = db.Column(db.String(100))
    
    # Audit
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    animal = db.relationship('Animal', backref='milking_records')
    farm = db.relationship('Farm', backref='milking_records')
    recorder = db.relationship('User', foreign_keys=[recorded_by])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_milking_farm_date', 'farm_id', 'date'),
        Index('idx_milking_animal_date', 'animal_id', 'date'),
    )
    
    def __repr__(self):
        return f'<MilkingRecord animal={self.animal_id} date={self.date} qty={self.quantity}L>'


class MilkingSummary(db.Model):
    """Daily farm-level milk production summary."""
    __tablename__ = 'milking_summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    
    # Totals
    total_animals_milked = db.Column(db.Integer, default=0)
    total_quantity = db.Column(db.Float, default=0.0)  # liters
    average_per_animal = db.Column(db.Float, default=0.0)  # liters
    
    # By session
    morning_quantity = db.Column(db.Float, default=0.0)
    afternoon_quantity = db.Column(db.Float, default=0.0)
    evening_quantity = db.Column(db.Float, default=0.0)
    
    # Quality averages
    avg_fat_content = db.Column(db.Float)
    avg_protein_content = db.Column(db.Float)
    avg_quality_grade = db.Column(db.String(5))
    
    # Commercial
    total_revenue = db.Column(db.Numeric(12, 2))
    
    # Auto-generated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    farm = db.relationship('Farm', backref='milking_summaries')
    
    __table_args__ = (
        UniqueConstraint('farm_id', 'date', name='uq_farm_date_summary'),
        Index('idx_summary_farm_date', 'farm_id', 'date'),
    )
    
    def __repr__(self):
        return f'<MilkingSummary farm={self.farm_id} date={self.date} total={self.total_quantity}L>'


# ---------------------------------------------------------------------------
# FEED CONSUMPTION - Individual animal feed tracking
# ---------------------------------------------------------------------------

class AnimalFeedConsumption(db.Model):
    """Track feed consumption per animal for better monitoring."""
    __tablename__ = 'animal_feed_consumptions'
    
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    feed_id = db.Column(db.Integer, db.ForeignKey('feeds.id'), nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    
    # Consumption details
    date = db.Column(db.Date, nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)  # kg
    unit = db.Column(db.String(20), default='KG')
    
    # Cost tracking
    unit_cost = db.Column(db.Numeric(10, 2))
    total_cost = db.Column(db.Numeric(10, 2))
    
    # Context
    feeding_time = db.Column(db.String(20))  # MORNING, NOON, EVENING, NIGHT
    feeding_method = db.Column(db.String(50))  # MANUAL, AUTO_FEEDER, GRAZING
    
    # Notes
    notes = db.Column(db.Text)
    
    # Audit
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    animal = db.relationship('Animal', backref='feed_consumptions')
    feed = db.relationship('Feed', backref='animal_consumptions')
    farm = db.relationship('Farm', backref='feed_consumptions')
    recorder = db.relationship('User', foreign_keys=[recorded_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_feed_consumption_animal_date', 'animal_id', 'date'),
        Index('idx_feed_consumption_farm_date', 'farm_id', 'date'),
    )
    
    def __repr__(self):
        return f'<AnimalFeedConsumption animal={self.animal_id} feed={self.feed_id} qty={self.quantity}kg>'


# ---------------------------------------------------------------------------
# FEED ALERTS - Dashboard feed requirement alerts
# ---------------------------------------------------------------------------

class FeedAlert(db.Model):
    """Track feed stock alerts and requirements."""
    __tablename__ = 'feed_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    feed_id = db.Column(db.Integer, db.ForeignKey('feeds.id'), nullable=False)
    feed = db.relationship('Feed', backref='alerts')
    
    # Alert details
    alert_type = db.Column(db.String(30))  # LOW_STOCK, OUT_OF_STOCK, EXPIRING_SOON, EXPIRED
    severity = db.Column(db.String(20))  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Stock info
    current_stock = db.Column(db.Float)
    required_stock = db.Column(db.Float)
    days_remaining = db.Column(db.Integer)
    
    # Message
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    
    # Status
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    farm = db.relationship('Farm', backref='feed_alerts')
    feed = db.relationship('Feed', backref='alerts')
    resolver = db.relationship('User', foreign_keys=[resolved_by])
    
    def __repr__(self):
        return f'<FeedAlert {self.alert_type} farm={self.farm_id} feed={self.feed_id}>'


# ---------------------------------------------------------------------------
# ENHANCED TREATMENT CATEGORIES
# ---------------------------------------------------------------------------

class TreatmentCategory(db.Model):
    """Treatment categories for better organization."""
    __tablename__ = 'treatment_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))  # Bootstrap icon class
    color = db.Column(db.String(20))  # CSS color for UI
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    medications = db.relationship('MedicationTemplate', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<TreatmentCategory {self.code}>'


class MedicationTemplate(db.Model):
    """Pre-defined medication templates for quick treatment entry."""
    __tablename__ = 'medication_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('treatment_categories.id'))
    
    # Medication details
    name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200))
    manufacturer = db.Column(db.String(200))
    
    # Dosage info
    default_dosage = db.Column(db.String(100))
    dosage_unit = db.Column(db.String(20))  # ml, mg, tablets, etc.
    calculate_by_weight = db.Column(db.Boolean, default=False)
    dosage_per_kg = db.Column(db.Float)  # If calculate_by_weight is True
    
    # Administration
    administration_route = db.Column(db.String(50))  # ORAL, INJECTION, TOPICAL, IV
    frequency = db.Column(db.String(100))  # Once, Daily, Twice daily, Weekly
    default_duration_days = db.Column(db.Integer)
    
    # Common uses
    indications = db.Column(db.Text)
    contraindications = db.Column(db.Text)
    side_effects = db.Column(db.Text)
    
    # Withdrawal period (for food animals)
    withdrawal_period_days = db.Column(db.Integer)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    requires_prescription = db.Column(db.Boolean, default=False)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def calculate_dosage_for_animal(self, animal_weight):
        """Calculate dosage based on animal weight."""
        if self.calculate_by_weight and self.dosage_per_kg:
            return animal_weight * self.dosage_per_kg
        return None
    
    def __repr__(self):
        return f'<MedicationTemplate {self.name}>'
