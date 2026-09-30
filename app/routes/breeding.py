from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, BreedingRecord, Animal
from app.forms import BreedingForm
from app.decorators import farm_required, permission_required
from datetime import datetime, timedelta

breeding_bp = Blueprint('breeding', __name__)


@breeding_bp.route('/')
@login_required
@farm_required
@permission_required('view_breeding')
def list_breeding():
    farm_id = session['current_farm_id']
    records = BreedingRecord.query.filter_by(farm_id=farm_id).order_by(
        BreedingRecord.mating_date.desc().nullslast()
    ).all()
    return render_template('breeding/list.html', records=records)


@breeding_bp.route('/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_breeding')
def add_breeding():
    farm_id = session['current_farm_id']
    form = BreedingForm()
    females = Animal.query.filter_by(farm_id=farm_id, gender='FEMALE').filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT'])
    ).order_by(Animal.tag_no).all()
    males = Animal.query.filter_by(farm_id=farm_id, gender='MALE').filter(
        Animal.status == 'ACTIVE'
    ).order_by(Animal.tag_no).all()
    form.female_animal_id.choices = [(a.id, f'{a.tag_no} - {a.name or "Unnamed"}') for a in females]
    form.male_animal_id.choices = [(0, '-- Optional --')] + [
        (a.id, f'{a.tag_no} - {a.name or "Unnamed"}') for a in males
    ]
    if form.validate_on_submit():
        expected = form.expected_delivery_date.data
        if not expected and form.mating_date.data:
            expected = form.mating_date.data + timedelta(days=150)
        record = BreedingRecord(
            farm_id=farm_id,
            female_animal_id=form.female_animal_id.data,
            male_animal_id=form.male_animal_id.data or None,
            heat_date=form.heat_date.data,
            mating_date=form.mating_date.data,
            mating_method=form.mating_method.data,
            expected_delivery_date=expected,
            pregnancy_status=form.pregnancy_status.data,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(record)
        if form.pregnancy_status.data == 'CONFIRMED':
            female = db.session.get(Animal, form.female_animal_id.data)
            if female:
                female.status = 'PREGNANT'
        db.session.commit()
        flash('Breeding record saved.', 'success')
        return redirect(url_for('breeding.list_breeding'))
    return render_template('breeding/form.html', form=form, title='Add Breeding Record')
