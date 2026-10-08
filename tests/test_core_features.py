from datetime import date, datetime, timedelta
from decimal import Decimal

from app.forms import TreatmentForm, VaccinationForm
from app import _sync_organization_owner_flags
from app.routes.animals import _government_tag_previews, _government_tag_prefix, _next_government_tag
from app.models import (
    Animal, AnimalFeedConsumption, Breed, Farm, Feed, Organization, Role,
    CommonMedicine, Species, StaffMembership, SubscriptionPlan, User, UserInvitation, db,
)
from app.routes.health import _medicine_similarity


def test_health_dropdown_choices(app):
    with app.app_context():
        medicine_values = {value for value, _ in TreatmentForm().medicine.choices}
        vaccine_values = {value for value, _ in VaccinationForm().vaccine.choices}

    assert {'DEWORMING', 'CALCIUM_VITAMIN', 'GENERAL_MEDICINE'} <= medicine_values
    assert {'FMD', 'LSD', 'HS', 'BQ', 'ANTHRAX', 'PPR', 'GOAT_POX', 'ENTEROTOXEMIA'} <= vaccine_values


def test_common_medicines_schema_and_similarity(app):
    with app.app_context():
        assert 'common_medicines' in db.metadata.tables
        assert CommonMedicine.__table__.columns['farm_id'].nullable is False

    close_match = _medicine_similarity('fever cough', 'Fever and coughing with loss of appetite')
    unrelated_match = _medicine_similarity('fever cough', 'Hoof injury and lameness')
    assert close_match > unrelated_match
    assert close_match >= 0.18


def test_added_cattle_breeds_have_government_tag_logic(app):
    with app.app_context():
        cattle = Species.query.filter_by(name='Cattle').one()
        breeds = {
            breed.name: breed
            for breed in Breed.query.filter_by(species_id=cattle.id).all()
        }
        added_breeds = {name: breeds[name] for name in ('Girlando', 'CBJ', 'PJ')}
        previews = _government_tag_previews(added_breeds.values())

        assert {
            name: _government_tag_prefix(breed)
            for name, breed in added_breeds.items()
        } == {'Girlando': 'CG', 'CBJ': 'CC', 'PJ': 'CP'}
        assert {
            name: previews[str(breed.id)]
            for name, breed in added_breeds.items()
        } == {'Girlando': 'CG 0001', 'CBJ': 'CC 0001', 'PJ': 'CP 0001'}
        assert {
            name: _next_government_tag(breed)
            for name, breed in added_breeds.items()
        } == {'Girlando': 'CG 0001', 'CBJ': 'CC 0001', 'PJ': 'CP 0001'}


def test_staff_cannot_open_farm_setup(app, client):
    with app.app_context():
        user = User(username='staff', email='staff@example.com', first_name='Farm', last_name='Staff')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

    response = client.post('/login', data={'username': 'staff', 'password': 'password123'}, follow_redirects=False)
    assert response.status_code == 302
    response = client.get('/onboarding/setup/farm', follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith('/select-farm')


def test_organization_signup_always_creates_owner(app, client):
    response = client.post('/register', data={
        'username': 'newowner',
        'email': 'newowner@example.com',
        'first_name': 'Farm',
        'last_name': 'Owner',
        'password': 'password123',
        'password2': 'password123',
        'organization_name': 'New Farm',
        'organization_slug': 'new-farm',
        'account_type': 'ADMIN',
    })

    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(username='newowner').one()
        assert user.is_organization_owner
        assert user.is_organization_admin


def test_role_specific_logins_enforce_owner_admin_hierarchy(app, client):
    with app.app_context():
        owner = User(username='owner', email='owner@example.com', is_organization_owner=True,
                     is_organization_admin=True)
        owner.set_password('password123')
        admin = User(username='admin', email='admin@example.com', is_organization_admin=True)
        admin.set_password('password123')
        db.session.add_all([owner, admin])
        db.session.commit()

    response = client.post('/admin/login', data={'username': 'owner', 'password': 'password123'})
    assert response.status_code == 200
    assert b'Invalid username or password for this login.' in response.data

    response = client.post('/owner/login', data={'username': 'admin', 'password': 'password123'})
    assert response.status_code == 200
    assert b'Invalid username or password for this login.' in response.data

    response = client.post('/owner/login', data={'username': 'owner', 'password': 'password123'})
    assert response.status_code == 302


def test_recorded_organization_owner_is_promoted_from_legacy_flags(app):
    with app.app_context():
        plan = SubscriptionPlan(name='Owner Sync Test', slug='owner-sync-test', trial_days=14)
        user = User(username='legacyowner', email='legacyowner@example.com')
        user.set_password('password123')
        db.session.add_all([plan, user])
        db.session.flush()
        organization = Organization(name='Legacy Farm', slug='legacy-farm', owner_id=user.id,
                                    subscription_plan_id=plan.id, subscription_status='TRIAL')
        db.session.add(organization)
        db.session.commit()

        _sync_organization_owner_flags()

        assert user.is_organization_owner
        assert user.is_organization_admin


def test_invited_administrator_receives_admin_account(app, client):
    with app.app_context():
        plan = SubscriptionPlan(name='Invitation Test', slug='invitation-test', trial_days=14)
        owner = User(username='inviteowner', email='inviteowner@example.com', is_organization_owner=True,
                     is_organization_admin=True)
        owner.set_password('password123')
        db.session.add_all([plan, owner])
        db.session.flush()
        organization = Organization(name='Invitation Farm', slug='invitation-farm', owner_id=owner.id,
                                    subscription_plan_id=plan.id, subscription_status='TRIAL')
        db.session.add(organization)
        db.session.flush()
        owner.organization_id = organization.id
        invitation = UserInvitation(
            organization_id=organization.id,
            email='farmadmin@example.com',
            token='admin-invitation-token',
            invited_by=owner.id,
            role_code='ADMIN',
            farm_ids=[],
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(invitation)
        db.session.commit()

    response = client.post('/invitation/admin-invitation-token', data={
        'username': 'farmadmin',
        'first_name': 'Farm',
        'last_name': 'Admin',
        'password': 'password123',
        'password2': 'password123',
    })

    assert response.status_code == 302
    with app.app_context():
        admin = User.query.filter_by(username='farmadmin').one()
        assert admin.is_organization_admin
        assert not admin.is_organization_owner


def test_staff_can_register_and_wait_for_owner_assignment(app, client):
    with app.app_context():
        plan = SubscriptionPlan(name='Staff Signup Test', slug='staff-signup-test', trial_days=14)
        owner = User(
            username='staffsignupowner',
            email='staffsignupowner@example.com',
            is_organization_owner=True,
            is_organization_admin=True,
        )
        owner.set_password('password123')
        db.session.add_all([plan, owner])
        db.session.flush()
        organization = Organization(
            name='Staff Signup Farm',
            slug='staff-signup-farm',
            owner_id=owner.id,
            subscription_plan_id=plan.id,
            subscription_status='TRIAL',
            trial_ends_at=datetime.utcnow() + timedelta(days=14),
        )
        db.session.add(organization)
        db.session.flush()
        owner.organization_id = organization.id
        farm = Farm(organization_id=organization.id, name='Main Farm', code='STAFF-1')
        db.session.add(farm)
        db.session.flush()
        owner_role = Role.query.filter_by(code='OWNER').one()
        db.session.add(StaffMembership(
            user_id=owner.id,
            farm_id=farm.id,
            role_id=owner_role.id,
            joining_date=date.today(),
            is_active=True,
        ))
        db.session.commit()
        farm_id = farm.id
        admin_role_id = Role.query.filter_by(code='ADMIN').one().id

    response = client.post('/register/staff', data={
        'username': 'newstaff',
        'email': 'newstaff@example.com',
        'first_name': 'New',
        'last_name': 'Staff',
        'organization_slug': 'staff-signup-farm',
        'password': 'password123',
        'password2': 'password123',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'you do not have farm access yet' in response.data
    with app.app_context():
        staff_user = User.query.filter_by(username='newstaff').one()
        assert not staff_user.is_organization_owner
        assert not staff_user.is_organization_admin
        assert staff_user.organization.slug == 'staff-signup-farm'
        assert staff_user.get_memberships() == []

    client.get('/logout')
    login_response = client.post('/owner/login', data={
        'username': 'staffsignupowner',
        'password': 'password123',
    })
    assert login_response.status_code == 302, login_response.get_data(as_text=True)
    assert login_response.location.endswith('/onboarding/setup-wizard')
    response = client.get('/organization/members')
    assert response.status_code == 200, f'Redirected to {response.location}'
    assert b'Awaiting farm assignment' in response.data
    assert b'newstaff' in response.data

    with client.session_transaction() as session_data:
        session_data['current_farm_id'] = farm_id
    response = client.post('/staff/add', data={
        'username': 'newstaff',
        'role_id': admin_role_id,
    })
    assert response.status_code == 302
    with app.app_context():
        membership = StaffMembership.query.filter_by(user_id=staff_user.id, farm_id=farm_id).one()
        assert membership.role.code == 'ADMIN'

    client.get('/logout')
    response = client.post('/admin/login', data={
        'username': 'newstaff',
        'password': 'password123',
    })
    assert response.status_code == 302
    assert response.location.endswith('/dashboard')


def test_owner_can_create_farms_up_to_five(app, client):
    with app.app_context():
        plan = SubscriptionPlan(name='Farm Cap Test', slug='farm-cap-test', trial_days=14)
        owner = User(
            username='farmowner',
            email='farmowner@example.com',
            is_organization_owner=True,
            is_organization_admin=True,
        )
        owner.set_password('password123')
        db.session.add_all([plan, owner])
        db.session.flush()
        organization = Organization(
            name='Multi Farm Org',
            slug='multi-farm-org',
            owner_id=owner.id,
            subscription_plan_id=plan.id,
            subscription_status='TRIAL',
            setup_completed=True,
        )
        db.session.add(organization)
        db.session.flush()
        owner.organization_id = organization.id
        db.session.add(Farm(organization_id=organization.id, name='Farm 1', code='MF-1'))
        db.session.commit()

    client.post('/owner/login', data={'username': 'farmowner', 'password': 'password123'})
    response = client.post('/onboarding/setup/farm', data={
        'name': 'Farm 2',
        'code': 'MF-2',
        'status': 'ACTIVE',
    })
    assert response.status_code == 302
    assert response.location.endswith('/select-farm')

    with app.app_context():
        organization = Organization.query.filter_by(slug='multi-farm-org').one()
        assert organization.farms.count() == 2
        for farm_number in range(3, 6):
            db.session.add(Farm(
                organization_id=organization.id,
                name=f'Farm {farm_number}',
                code=f'MF-{farm_number}',
            ))
        db.session.commit()
        assert not organization.can_add_farm()

    response = client.post('/onboarding/setup/farm', data={
        'name': 'Farm 6',
        'code': 'MF-6',
        'status': 'ACTIVE',
    })
    assert response.status_code == 302
    with app.app_context():
        organization = Organization.query.filter_by(slug='multi-farm-org').one()
        assert organization.farms.count() == 5


def test_staff_can_view_and_switch_between_assigned_farms(app, client):
    with app.app_context():
        plan = SubscriptionPlan(name='Farm Switch Test', slug='farm-switch-test', trial_days=14)
        owner = User(
            username='switchowner',
            email='switchowner@example.com',
            is_organization_owner=True,
            is_organization_admin=True,
        )
        owner.set_password('password123')
        staff_user = User(username='switchstaff', email='switchstaff@example.com')
        staff_user.set_password('password123')
        db.session.add_all([plan, owner, staff_user])
        db.session.flush()
        organization = Organization(
            name='Switch Farm Org',
            slug='switch-farm-org',
            owner_id=owner.id,
            subscription_plan_id=plan.id,
            subscription_status='TRIAL',
        )
        db.session.add(organization)
        db.session.flush()
        owner.organization_id = organization.id
        staff_user.organization_id = organization.id
        first_farm = Farm(organization_id=organization.id, name='North Farm', code='SW-N')
        second_farm = Farm(organization_id=organization.id, name='South Farm', code='SW-S')
        db.session.add_all([first_farm, second_farm])
        db.session.flush()
        role = Role.query.filter_by(code='FARM_STAFF').one()
        db.session.add_all([
            StaffMembership(user_id=staff_user.id, farm_id=first_farm.id, role_id=role.id,
                            joining_date=date.today(), is_active=True),
            StaffMembership(user_id=staff_user.id, farm_id=second_farm.id, role_id=role.id,
                            joining_date=date.today(), is_active=True),
        ])
        db.session.commit()
        second_farm_id = second_farm.id

    client.post('/staff/login', data={'username': 'switchstaff', 'password': 'password123'})
    response = client.get('/select-farm')
    assert response.status_code == 200
    assert b'North Farm' in response.data, response.get_data(as_text=True)
    assert b'South Farm' in response.data

    response = client.post('/select-farm', data={'farm_id': second_farm_id})
    assert response.status_code == 302
    with client.session_transaction() as session_data:
        assert session_data['current_farm_id'] == second_farm_id


def test_assigning_existing_staff_to_another_farm_does_not_use_another_staff_slot(app, client):
    with app.app_context():
        plan = SubscriptionPlan(name='Shared Staff Test', slug='shared-staff-test', trial_days=14)
        owner = User(
            username='sharedowner',
            email='sharedowner@example.com',
            is_organization_owner=True,
            is_organization_admin=True,
        )
        owner.set_password('password123')
        staff_user = User(username='sharedstaff', email='sharedstaff@example.com')
        staff_user.set_password('password123')
        db.session.add_all([plan, owner, staff_user])
        db.session.flush()
        organization = Organization(
            name='Shared Staff Org',
            slug='shared-staff-org',
            owner_id=owner.id,
            subscription_plan_id=plan.id,
            subscription_status='TRIAL',
            max_staff=1,
        )
        db.session.add(organization)
        db.session.flush()
        owner.organization_id = organization.id
        staff_user.organization_id = organization.id
        first_farm = Farm(organization_id=organization.id, name='First Farm', code='SH-1')
        second_farm = Farm(organization_id=organization.id, name='Second Farm', code='SH-2')
        db.session.add_all([first_farm, second_farm])
        db.session.flush()
        owner_role = Role.query.filter_by(code='OWNER').one()
        staff_role = Role.query.filter_by(code='FARM_STAFF').one()
        db.session.add_all([
            StaffMembership(user_id=owner.id, farm_id=first_farm.id, role_id=owner_role.id,
                            joining_date=date.today(), is_active=True),
            StaffMembership(user_id=owner.id, farm_id=second_farm.id, role_id=owner_role.id,
                            joining_date=date.today(), is_active=True),
            StaffMembership(user_id=staff_user.id, farm_id=first_farm.id, role_id=staff_role.id,
                            joining_date=date.today(), is_active=True),
        ])
        db.session.commit()
        second_farm_id = second_farm.id
        staff_role_id = staff_role.id
        staff_user_id = staff_user.id

    client.post('/owner/login', data={'username': 'sharedowner', 'password': 'password123'})
    with client.session_transaction() as session_data:
        session_data['current_farm_id'] = second_farm_id
    response = client.post('/staff/add', data={
        'username': 'sharedstaff',
        'role_id': staff_role_id,
    })

    assert response.status_code == 302
    with app.app_context():
        memberships = StaffMembership.query.filter_by(user_id=staff_user_id, is_active=True).all()
        assert len(memberships) == 2


def test_expected_routes_are_registered(app):
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert '/milking/' in routes
    assert '/milking/record' in routes
    assert '/reports/<section>/<file_format>' in routes
    assert '/admin/roles/add' in routes


def test_animal_feed_consumption_model_tracks_farm_and_quantity(app):
    with app.app_context():
        plan = SubscriptionPlan(name='Test', slug='test', trial_days=14)
        db.session.add(plan)
        db.session.flush()
        owner = User(username='owner', email='owner@example.com', first_name='Farm', last_name='Owner',
                     is_organization_owner=True, is_organization_admin=True)
        owner.set_password('password123')
        db.session.add(owner)
        db.session.flush()
        organization = Organization(name='Test Farm', slug='test-farm', owner_id=owner.id,
                                    subscription_plan_id=plan.id, subscription_status='TRIAL')
        db.session.add(organization)
        db.session.flush()
        owner.organization_id = organization.id
        farm = Farm(organization_id=organization.id, name='Main Farm', code='TEST-1')
        db.session.add(farm)
        species = Species.query.filter_by(name='Cattle').first()
        breed = Breed(species_id=species.id, name='Test Jersey')
        db.session.add(breed)
        db.session.flush()
        animal = Animal(farm_id=farm.id, tag_no='A-1', gender='FEMALE', breed_id=breed.id,
                        status='ACTIVE', current_weight=Decimal('300'))
        feed = Feed(farm_id=farm.id, feed_name='Hay', unit='KG', stock_quantity=Decimal('20'), minimum_stock=Decimal('5'))
        db.session.add_all([animal, feed])
        db.session.flush()
        record = AnimalFeedConsumption(animal_id=animal.id, feed_id=feed.id, farm_id=farm.id,
                                       date=date.today(), quantity=3, unit='KG', recorded_by=owner.id)
        db.session.add(record)
        db.session.commit()

        assert record.farm_id == farm.id
        assert record.quantity == 3
        assert animal.calculate_daily_feed_requirement() == 9.0
