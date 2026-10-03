from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user
from app.models import db, Animal, AnimalFeedConsumption, Feed, Breed, Location, Species, AnimalWeight, AnimalMovement, Expense
from app.forms import AnimalForm, AnimalFeedConsumptionForm, LocationForm
from app.decorators import farm_required, permission_required
from datetime import datetime
from decimal import Decimal

animals_bp = Blueprint('animals', __name__)


@animals_bp.route('/')
@login_required
@farm_required
@permission_required('view_animals')
def list_animals():
    farm_id = session['current_farm_id']
    status = request.args.get('status', '')
    gender = request.args.get('gender', '')
    breed_id = request.args.get('breed_id', type=int)
    species_id = request.args.get('species_id', type=int)
    q = Animal.query.filter_by(farm_id=farm_id)
    if status:
        q = q.filter_by(status=status)
    if gender:
        q = q.filter_by(gender=gender)
    if breed_id:
        q = q.filter_by(breed_id=breed_id)
    if species_id:
        q = q.join(Breed).filter(Breed.species_id == species_id)
    animals = q.order_by(Animal.tag_no).all()
    breeds = Breed.query.join(Species).order_by(Species.name, Breed.name).all()
    species = Species.query.order_by(Species.name).all()
    return render_template('animals/list.html', animals=animals, status=status, gender=gender,
                           breed_id=breed_id, species_id=species_id, breeds=breeds, species=species)


@animals_bp.route('/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_animals')
def add_animal():
    farm_id = session['current_farm_id']
    form = AnimalForm()
    form.breed_id.choices = [(b.id, f'{b.species.name} - {b.name}') for b in
                             Breed.query.join(Species).order_by(Species.name, Breed.name).all()]
    form.location_id.choices = [(0, '-- Select --')] + [
        (l.id, l.name) for l in Location.query.filter_by(farm_id=farm_id, is_active=True).all()
    ]
    form.feed_id.choices = [(0, '-- No assigned feed --')] + [
        (f.id, f'{f.feed_name} ({f.unit})') for f in Feed.query.filter_by(farm_id=farm_id).order_by(Feed.feed_name).all()
    ]
    if form.validate_on_submit():
        # Check unique tag
        exists = Animal.query.filter_by(farm_id=farm_id, tag_no=form.tag_no.data).first()
        if exists:
            flash('Tag number already exists for this farm.', 'danger')
            return render_template('animals/form.html', form=form, title='Add Animal')
        animal = Animal(
            farm_id=farm_id,
            tag_no=form.tag_no.data,
            name=form.name.data,
            gender=form.gender.data,
            breed_id=form.breed_id.data,
            date_of_birth=form.date_of_birth.data,
            color=form.color.data,
            birth_weight=form.birth_weight.data,
            current_weight=form.current_weight.data,
            purchase_date=form.purchase_date.data,
            purchase_price=form.purchase_price.data,
            feed_id=form.feed_id.data or None,
            daily_feed_quantity=form.daily_feed_quantity.data,
            source=form.source.data,
            location_id=form.location_id.data or None,
            status=form.status.data,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(animal)
        if animal.source == 'PURCHASED' and animal.purchase_price:
            db.session.add(Expense(
                farm_id=farm_id,
                expense_date=animal.purchase_date or datetime.utcnow().date(),
                category='ANIMAL_PURCHASE',
                description=f'Animal purchase: {animal.tag_no}',
                amount=animal.purchase_price,
                payment_mode='OTHER',
                remarks='Automatically recorded from animal purchase.',
                created_by=current_user.id,
                updated_by=current_user.id,
            ))
        db.session.commit()
        flash(f'Animal {animal.tag_no} added successfully.', 'success')
        return redirect(url_for('animals.list_animals'))
    return render_template('animals/form.html', form=form, title='Add Animal')


@animals_bp.route('/<int:id>')
@login_required
@farm_required
@permission_required('view_animals')
def view_animal(id):
    farm_id = session['current_farm_id']
    animal = Animal.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    weights = AnimalWeight.query.filter_by(animal_id=id).order_by(AnimalWeight.weight_date.desc()).limit(10).all()
    movements = AnimalMovement.query.filter_by(animal_id=id).order_by(AnimalMovement.movement_date.desc()).limit(10).all()
    feed_consumptions = AnimalFeedConsumption.query.filter_by(animal_id=id).order_by(
        AnimalFeedConsumption.date.desc(), AnimalFeedConsumption.id.desc()
    ).limit(20).all()
    return render_template('animals/view.html', animal=animal, weights=weights, movements=movements,
                           feed_consumptions=feed_consumptions)


@animals_bp.route('/<int:id>/feed', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_feed')
def add_feed_consumption(id):
    farm_id = session['current_farm_id']
    animal = Animal.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    form = AnimalFeedConsumptionForm()
    animals = Animal.query.filter_by(farm_id=farm_id).order_by(Animal.tag_no).all()
    feeds = Feed.query.filter_by(farm_id=farm_id).order_by(Feed.feed_name).all()
    form.animal_id.choices = [(a.id, f'{a.tag_no} - {a.name or "Unnamed"}') for a in animals]
    form.feed_id.choices = [(f.id, f'{f.feed_name} ({f.stock_quantity} {f.unit})') for f in feeds]
    if form.validate_on_submit():
        selected_animal = Animal.query.filter_by(id=form.animal_id.data, farm_id=farm_id).first()
        feed = Feed.query.filter_by(id=form.feed_id.data, farm_id=farm_id).first()
        quantity = Decimal(str(form.quantity.data))
        if not selected_animal or not feed:
            flash('Invalid animal or feed.', 'danger')
        elif Decimal(str(feed.stock_quantity or 0)) < quantity:
            flash(f'Insufficient stock. Available: {feed.stock_quantity} {feed.unit}.', 'danger')
        else:
            unit_cost = Decimal(str(feed.purchase_price)) if feed.purchase_price else None
            record = AnimalFeedConsumption(
                animal_id=selected_animal.id,
                feed_id=feed.id,
                farm_id=farm_id,
                date=form.date.data,
                quantity=float(quantity),
                unit=feed.unit or 'KG',
                unit_cost=unit_cost,
                total_cost=unit_cost * quantity if unit_cost else None,
                feeding_time=form.feeding_time.data,
                feeding_method=form.feeding_method.data,
                notes=form.notes.data,
                recorded_by=current_user.id,
            )
            feed.stock_quantity = Decimal(str(feed.stock_quantity or 0)) - quantity
            db.session.add(record)
            db.session.commit()
            flash('Animal feed consumption recorded and stock updated.', 'success')
            return redirect(url_for('animals.view_animal', id=selected_animal.id))
    return render_template('feed/animal_consumption_form.html', form=form, animal=animal,
                           title='Record Animal Feed Consumption')


@animals_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_animals')
def edit_animal(id):
    farm_id = session['current_farm_id']
    animal = Animal.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    form = AnimalForm(obj=animal)
    form.breed_id.choices = [(b.id, f'{b.species.name} - {b.name}') for b in
                             Breed.query.join(Species).order_by(Species.name, Breed.name).all()]
    form.location_id.choices = [(0, '-- Select --')] + [
        (l.id, l.name) for l in Location.query.filter_by(farm_id=farm_id, is_active=True).all()
    ]
    form.feed_id.choices = [(0, '-- No assigned feed --')] + [
        (f.id, f'{f.feed_name} ({f.unit})') for f in Feed.query.filter_by(farm_id=farm_id).order_by(Feed.feed_name).all()
    ]
    if form.validate_on_submit():
        other = Animal.query.filter(
            Animal.farm_id == farm_id, Animal.tag_no == form.tag_no.data, Animal.id != id
        ).first()
        if other:
            flash('Tag number already exists.', 'danger')
            return render_template('animals/form.html', form=form, title='Edit Animal', animal=animal)
        form.populate_obj(animal)
        if form.location_id.data == 0:
            animal.location_id = None
        animal.updated_by = current_user.id
        animal.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Animal updated successfully.', 'success')
        return redirect(url_for('animals.view_animal', id=id))
    return render_template('animals/form.html', form=form, title='Edit Animal', animal=animal)


@animals_bp.route('/locations')
@login_required
@farm_required
@permission_required('manage_locations')
def list_locations():
    farm_id = session['current_farm_id']
    locations = Location.query.filter_by(farm_id=farm_id).order_by(Location.name).all()
    return render_template('animals/locations.html', locations=locations)


@animals_bp.route('/locations/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_locations')
def add_location():
    farm_id = session['current_farm_id']
    form = LocationForm()
    if form.validate_on_submit():
        loc = Location(
            farm_id=farm_id,
            name=form.name.data,
            capacity=form.capacity.data,
            description=form.description.data,
            is_active=form.is_active.data,
        )
        db.session.add(loc)
        db.session.commit()
        flash('Location added.', 'success')
        return redirect(url_for('animals.list_locations'))
    return render_template('animals/location_form.html', form=form, title='Add Location')
