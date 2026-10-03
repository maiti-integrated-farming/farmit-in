from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user
from app.models import db, Vaccination, Treatment, Animal, Expense
from app.forms import VaccinationForm, TreatmentForm
from app.decorators import farm_required, permission_required
from datetime import datetime, timedelta
from sqlalchemy import and_, func

health_bp = Blueprint('health', __name__)


@health_bp.route('/vaccinations')
@login_required
@farm_required
@permission_required('view_health')
def list_vaccinations():
    farm_id = session['current_farm_id']
    breed_id = request.args.get('breed_id', type=int)
    species_id = request.args.get('species_id', type=int)
    query = Vaccination.query.join(Animal).filter(Vaccination.farm_id == farm_id)
    if breed_id:
        query = query.filter(Animal.breed_id == breed_id)
    if species_id:
        query = query.join(Animal.breed).filter_by(species_id=species_id)
    records = query.order_by(Vaccination.date.desc()).limit(100).all()
    from app.models import Breed, Species
    return render_template('health/vaccinations.html', records=records, breed_id=breed_id,
                           species_id=species_id, breeds=Breed.query.join(Species).all(),
                           species=Species.query.order_by(Species.name).all())


@health_bp.route('/vaccinations/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_health')
def add_vaccination():
    farm_id = session['current_farm_id']
    form = VaccinationForm()
    animals = Animal.query.filter_by(farm_id=farm_id).filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).order_by(Animal.tag_no).all()
    form.animal_id.choices = [(a.id, f'{a.tag_no} - {a.name or ""}') for a in animals]
    if form.validate_on_submit():
        animal = db.session.get(Animal, form.animal_id.data)
        if not animal or animal.farm_id != farm_id:
            flash('Invalid animal.', 'danger')
            return render_template('health/vaccination_form.html', form=form, title='Add Vaccination')
        species_name = (animal.breed.species.name if animal.breed and animal.breed.species else '').lower()
        cattle_vaccines = {'FMD', 'LSD', 'HS', 'BQ', 'ANTHRAX'}
        goat_vaccines = {'PPR', 'FMD', 'GOAT_POX', 'ENTEROTOXEMIA', 'HS'}
        allowed_vaccines = goat_vaccines if 'goat' in species_name else cattle_vaccines
        if form.vaccine.data not in allowed_vaccines:
            flash('Selected vaccine is not available for this animal type.', 'danger')
            return render_template('health/vaccination_form.html', form=form, title='Add Vaccination')
        rec = Vaccination(
            farm_id=farm_id,
            animal_id=form.animal_id.data,
            vaccine=form.vaccine.data,
            date=form.date.data,
            dose=form.dose.data,
            batch_no=form.batch_no.data,
            next_due_date=form.next_due_date.data,
            cost=form.cost.data,
            administered_by=current_user.id,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(rec)
        if rec.cost:
            db.session.add(Expense(
                farm_id=farm_id,
                expense_date=rec.date,
                category='VACCINE',
                description=f'Vaccination: {rec.vaccine} - {animal.tag_no}',
                amount=rec.cost,
                payment_mode='OTHER',
                remarks='Automatically recorded from vaccination record.',
                created_by=current_user.id,
                updated_by=current_user.id,
            ))
        db.session.commit()
        flash('Vaccination recorded.', 'success')
        return redirect(url_for('health.list_vaccinations'))
    return render_template('health/vaccination_form.html', form=form, title='Add Vaccination')


@health_bp.route('/treatments')
@login_required
@farm_required
@permission_required('view_health')
def list_treatments():
    farm_id = session['current_farm_id']
    breed_id = request.args.get('breed_id', type=int)
    species_id = request.args.get('species_id', type=int)
    query = Treatment.query.join(Animal).filter(Treatment.farm_id == farm_id)
    if breed_id:
        query = query.filter(Animal.breed_id == breed_id)
    if species_id:
        query = query.join(Animal.breed).filter_by(species_id=species_id)
    records = query.order_by(Treatment.date.desc()).limit(100).all()
    from app.models import Breed, Species
    return render_template('health/treatments.html', records=records, breed_id=breed_id,
                           species_id=species_id, breeds=Breed.query.join(Species).all(),
                           species=Species.query.order_by(Species.name).all())


@health_bp.route('/treatments/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_health')
def add_treatment():
    farm_id = session['current_farm_id']
    form = TreatmentForm()
    animals = Animal.query.filter_by(farm_id=farm_id).filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK', 'QUARANTINE'])
    ).order_by(Animal.tag_no).all()
    form.animal_id.choices = [(a.id, f'{a.tag_no} - {a.name or ""}') for a in animals]
    if form.validate_on_submit():
        rec = Treatment(
            farm_id=farm_id,
            animal_id=form.animal_id.data,
            date=form.date.data,
            symptoms=form.symptoms.data,
            diagnosis=form.diagnosis.data,
            medicine=form.medicine.data,
            treatment_type=form.medicine.data or 'GENERAL_MEDICINE',
            dose=form.dose.data,
            vet=current_user.id,
            follow_up_date=form.follow_up_date.data,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(rec)
        animal = db.session.get(Animal, form.animal_id.data)
        if animal and animal.status == 'ACTIVE':
            animal.status = 'SICK'
        db.session.commit()
        flash('Treatment recorded. Animal status set to SICK if previously ACTIVE.', 'success')
        return redirect(url_for('health.list_treatments'))
    return render_template('health/treatment_form.html', form=form, title='Add Treatment')



# =============================================================================
# ENHANCED TREATMENTS WITH CATEGORIES
# =============================================================================

@health_bp.route('/treatments/enhanced')
@login_required
@farm_required
def list_enhanced_treatments():
    """List treatments with category filtering."""
    from app.models import TreatmentCategory
    
    farm_id = session['current_farm_id']
    
    # Get filter parameters
    category_id = request.args.get('category_id', type=int)
    animal_id = request.args.get('animal_id', type=int)
    
    # Base query
    query = Treatment.query.filter_by(farm_id=farm_id)
    
    # Apply filters
    if category_id:
        query = query.filter_by(category_id=category_id)
    if animal_id:
        query = query.filter_by(animal_id=animal_id)
    
    # Get treatments
    treatments = query.order_by(Treatment.date.desc()).limit(100).all()
    
    # Get categories for filtering
    categories = TreatmentCategory.query.filter_by(is_active=True).order_by(TreatmentCategory.sort_order).all()
    
    # Get animals for filtering
    animals = Animal.query.filter_by(farm_id=farm_id).order_by(Animal.tag_no).all()
    
    # Calculate category stats
    category_stats = db.session.query(
        TreatmentCategory.code,
        TreatmentCategory.name,
        TreatmentCategory.color,
        func.count(Treatment.id).label('count')
    ).outerjoin(Treatment, and_(
        Treatment.category_id == TreatmentCategory.id,
        Treatment.farm_id == farm_id
    )).group_by(TreatmentCategory.id).all()
    
    return render_template('health/enhanced_treatments.html',
                         treatments=treatments,
                         categories=categories,
                         animals=animals,
                         category_stats=category_stats,
                         filters={'category_id': category_id, 'animal_id': animal_id})


@health_bp.route('/treatments/enhanced/add', methods=['GET', 'POST'])
@login_required
@farm_required
def add_enhanced_treatment():
    """Add treatment with category and template support."""
    from app.models import TreatmentCategory, MedicationTemplate, User
    from app.forms import EnhancedTreatmentForm
    
    farm_id = session['current_farm_id']
    form = EnhancedTreatmentForm()
    
    # Populate choices
    animals = Animal.query.filter_by(farm_id=farm_id).order_by(Animal.tag_no).all()
    form.animal_id.choices = [(0, 'Select Animal')] + [(a.id, f"{a.tag_no} - {a.name or 'Unnamed'}") for a in animals]
    
    categories = TreatmentCategory.query.filter_by(is_active=True).order_by(TreatmentCategory.sort_order).all()
    form.category_id.choices = [(0, 'Select Category')] + [(c.id, c.name) for c in categories]
    
    templates = MedicationTemplate.query.filter_by(is_active=True).order_by(MedicationTemplate.name).all()
    form.medication_template_id.choices = [(0, 'No Template')] + [(t.id, t.name) for t in templates]
    
    vets = User.query.filter_by(organization_id=current_user.organization_id).all()
    form.vet.choices = [(0, 'Not Assigned')] + [(v.id, v.full_name) for v in vets]
    
    if form.validate_on_submit():
        # Calculate withdrawal end date if withdrawal period provided
        withdrawal_end_date = None
        if form.withdrawal_period_days.data:
            withdrawal_end_date = form.date.data + timedelta(days=form.withdrawal_period_days.data)
        
        # Calculate next dose date if frequency and duration provided
        next_dose_date = None
        if form.frequency.data and form.frequency.data != 'ONCE':
            if form.frequency.data == 'DAILY':
                next_dose_date = form.date.data + timedelta(days=1)
            elif form.frequency.data in ['TWICE_DAILY', 'THREE_TIMES_DAILY']:
                next_dose_date = form.date.data  # Same day
            elif form.frequency.data == 'WEEKLY':
                next_dose_date = form.date.data + timedelta(days=7)
        
        treatment = Treatment(
            farm_id=farm_id,
            animal_id=form.animal_id.data,
            category_id=form.category_id.data if form.category_id.data else None,
            medication_template_id=form.medication_template_id.data if form.medication_template_id.data else None,
            date=form.date.data,
            medicine=form.medicine.data,
            dose=form.dose.data,
            dosage_unit=form.dosage_unit.data,
            administration_route=form.administration_route.data,
            frequency=form.frequency.data,
            duration_days=form.duration_days.data,
            next_dose_date=next_dose_date,
            symptoms=form.symptoms.data,
            diagnosis=form.diagnosis.data,
            vet=form.vet.data if form.vet.data else None,
            follow_up_date=form.follow_up_date.data,
            cost=form.cost.data,
            withdrawal_period_days=form.withdrawal_period_days.data,
            withdrawal_end_date=withdrawal_end_date,
            remarks=form.remarks.data,
            created_by=current_user.id
        )
        
        db.session.add(treatment)
        db.session.commit()
        
        flash('Treatment recorded successfully', 'success')
        return redirect(url_for('health.list_enhanced_treatments'))
    
    # Set defaults
    if not form.date.data:
        form.date.data = datetime.now().date()
    
    return render_template('health/enhanced_treatment_form.html', form=form)


@health_bp.route('/medications/templates')
@login_required
@farm_required
def list_medication_templates():
    """List medication templates."""
    from app.models import MedicationTemplate, TreatmentCategory
    
    category_id = request.args.get('category_id', type=int)
    
    query = MedicationTemplate.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    templates = query.order_by(MedicationTemplate.name).all()
    categories = TreatmentCategory.query.filter_by(is_active=True).order_by(TreatmentCategory.sort_order).all()
    
    return render_template('health/medication_templates.html',
                         templates=templates,
                         categories=categories,
                         filter_category_id=category_id)


@health_bp.route('/medications/templates/add', methods=['GET', 'POST'])
@login_required
@farm_required
def add_medication_template():
    """Add new medication template (admin only)."""
    from app.models import TreatmentCategory
    from app.forms import MedicationTemplateForm
    
    # Only owners and admins can create templates
    if not (current_user.is_organization_owner or current_user.is_organization_admin):
        flash('Only administrators can create medication templates', 'danger')
        return redirect(url_for('health.list_medication_templates'))
    
    form = MedicationTemplateForm()
    
    categories = TreatmentCategory.query.filter_by(is_active=True).order_by(TreatmentCategory.sort_order).all()
    form.category_id.choices = [(c.id, c.name) for c in categories]
    
    if form.validate_on_submit():
        from app.models import MedicationTemplate
        
        template = MedicationTemplate(
            category_id=form.category_id.data,
            name=form.name.data,
            generic_name=form.generic_name.data,
            manufacturer=form.manufacturer.data,
            default_dosage=form.default_dosage.data,
            dosage_unit=form.dosage_unit.data,
            calculate_by_weight=form.calculate_by_weight.data,
            dosage_per_kg=float(form.dosage_per_kg.data) if form.dosage_per_kg.data else None,
            administration_route=form.administration_route.data,
            frequency=form.frequency.data,
            default_duration_days=form.default_duration_days.data,
            indications=form.indications.data,
            contraindications=form.contraindications.data,
            side_effects=form.side_effects.data,
            withdrawal_period_days=form.withdrawal_period_days.data,
            is_active=form.is_active.data,
            requires_prescription=form.requires_prescription.data
        )
        
        db.session.add(template)
        db.session.commit()
        
        flash(f'Medication template "{template.name}" created successfully', 'success')
        return redirect(url_for('health.list_medication_templates'))
    
    return render_template('health/medication_template_form.html', form=form)
