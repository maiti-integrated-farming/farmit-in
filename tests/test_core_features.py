from datetime import date
from decimal import Decimal

from app.forms import TreatmentForm, VaccinationForm
from app.models import (
    Animal, AnimalFeedConsumption, Breed, Farm, Feed, Organization, Role,
    Species, StaffMembership, SubscriptionPlan, User, db,
)


def test_health_dropdown_choices(app):
    with app.app_context():
        medicine_values = {value for value, _ in TreatmentForm().medicine.choices}
        vaccine_values = {value for value, _ in VaccinationForm().vaccine.choices}

    assert {'DEWORMING', 'CALCIUM_VITAMIN', 'GENERAL_MEDICINE'} <= medicine_values
    assert {'FMD', 'LSD', 'HS', 'BQ', 'ANTHRAX', 'PPR', 'GOAT_POX', 'ENTEROTOXEMIA'} <= vaccine_values


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
    assert response.location.endswith('/dashboard')


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
