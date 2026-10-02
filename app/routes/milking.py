"""
Milking Module Routes
Handles milk production tracking and reporting.
"""

from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_
from app.models import (
    db, Farm, Animal, MilkingRecord, MilkingSummary, Breed
)
from app.forms import MilkingRecordForm, MilkingFilterForm
from app.decorators import farm_required, permission_required

milking_bp = Blueprint('milking', __name__)


@milking_bp.route('/')
@login_required
@farm_required
@permission_required('view_milking')
def list_milking_records():
    """List all milking records with filtering."""
    farm_id = session.get('current_farm_id')
    farm = db.session.get(Farm, farm_id)
    
    # Get filter parameters
    animal_id = request.args.get('animal_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    session_filter = request.args.get('session')
    quality_grade = request.args.get('quality_grade')
    
    # Base query
    query = MilkingRecord.query.filter_by(farm_id=farm_id)
    
    # Apply filters
    if animal_id:
        query = query.filter_by(animal_id=animal_id)
    if date_from:
        query = query.filter(MilkingRecord.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    if date_to:
        query = query.filter(MilkingRecord.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    if session_filter:
        query = query.filter_by(session=session_filter)
    if quality_grade:
        query = query.filter_by(quality_grade=quality_grade)
    
    # Order and paginate
    page = request.args.get('page', 1, type=int)
    records = query.order_by(MilkingRecord.date.desc(), MilkingRecord.session.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get animals for filter dropdown
    animals = Animal.query.filter_by(farm_id=farm_id, gender='FEMALE').order_by(Animal.tag_no).all()
    filter_form = MilkingFilterForm()
    filter_form.animal_id.choices = [(0, 'All Animals')] + [(a.id, f'{a.tag_no} - {a.name or "Unnamed"}') for a in animals]
    
    # Calculate summary stats for current view
    summary_query = query.with_entities(
        func.count(MilkingRecord.id).label('total_records'),
        func.sum(MilkingRecord.quantity).label('total_quantity'),
        func.avg(MilkingRecord.quantity).label('avg_quantity'),
        func.sum(MilkingRecord.total_amount).label('total_revenue')
    ).first()
    
    summary = {
        'total_records': summary_query.total_records or 0,
        'total_quantity': float(summary_query.total_quantity or 0),
        'avg_quantity': float(summary_query.avg_quantity or 0),
        'total_revenue': float(summary_query.total_revenue or 0)
    }
    today_summary = {
        'total_quantity': summary['total_quantity'],
        'animals_milked': summary['total_records'],
        'avg_quality': 0,
        'sessions': summary['total_records'],
    }
    
    return render_template('milking/list.html',
                         farm=farm,
                         records=records,
                         animals=animals,
                         filter_form=filter_form,
                         summary=summary,
                         today_summary=today_summary,
                         filters={
                             'animal_id': animal_id,
                             'date_from': date_from,
                             'date_to': date_to,
                             'session': session_filter,
                             'quality_grade': quality_grade
                         })


@milking_bp.route('/record', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_milking')
def add_milking_record():
    """Add new milking record."""
    farm_id = session.get('current_farm_id')
    farm = db.session.get(Farm, farm_id)
    
    form = MilkingRecordForm()
    
    # Populate animal choices (only female animals)
    animals = Animal.query.filter(
        and_(
            Animal.farm_id == farm_id,
            Animal.gender == 'FEMALE',
            Animal.status.in_(['ACTIVE', 'LACTATING', 'MILKING', 'PREGNANT'])
        )
    ).order_by(Animal.tag_no).all()
    
    form.animal_id.choices = [(0, 'Select Animal')] + [
        (a.id, f"{a.tag_no} - {a.name or 'Unnamed'}") for a in animals
    ]
    
    if form.validate_on_submit():
        duplicate = MilkingRecord.query.filter_by(
            farm_id=farm_id, animal_id=form.animal_id.data,
            date=form.date.data, session=form.session.data
        ).first()
        if duplicate:
            flash('A milking record already exists for this animal, date, and session.', 'warning')
            return render_template('milking/record_form.html', form=form, farm=farm)
        # Calculate total amount if price provided
        total_amount = None
        if form.price_per_liter.data and form.quantity.data:
            total_amount = float(form.price_per_liter.data) * float(form.quantity.data)
        
        record = MilkingRecord(
            animal_id=form.animal_id.data,
            farm_id=farm_id,
            date=form.date.data,
            session=form.session.data,
            quantity=float(form.quantity.data),
            fat_content=float(form.fat_content.data) if form.fat_content.data else None,
            protein_content=float(form.protein_content.data) if form.protein_content.data else None,
            lactose_content=float(form.lactose_content.data) if form.lactose_content.data else None,
            snf=float(form.snf.data) if form.snf.data else None,
            density=float(form.density.data) if form.density.data else None,
            temperature=float(form.temperature.data) if form.temperature.data else None,
            quality_grade=form.quality_grade.data if form.quality_grade.data else None,
            price_per_liter=form.price_per_liter.data,
            total_amount=total_amount,
            notes=form.notes.data,
            anomalies=form.anomalies.data,
            recorded_by=current_user.id
        )
        
        db.session.add(record)
        db.session.commit()
        
        # Update daily summary
        update_daily_summary(farm_id, form.date.data)
        
        flash(f'Milk production recorded: {form.quantity.data}L from {record.animal.tag_no}', 'success')
        return redirect(url_for('milking.list_milking_records'))
    
    # Set default date to today
    if not form.date.data:
        form.date.data = date.today()
    
    return render_template('milking/record_form.html', form=form, farm=farm)


@milking_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_milking')
def edit_milking_record(id):
    """Edit existing milking record."""
    farm_id = session.get('current_farm_id')
    farm = db.session.get(Farm, farm_id)
    
    record = MilkingRecord.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    
    form = MilkingRecordForm(obj=record)
    
    # Populate animal choices
    animals = Animal.query.filter_by(farm_id=farm_id, gender='FEMALE').order_by(Animal.tag_no).all()
    form.animal_id.choices = [(a.id, f"{a.tag_no} - {a.name or 'Unnamed'}") for a in animals]
    
    if form.validate_on_submit():
        old_date = record.date
        # Update record
        record.animal_id = form.animal_id.data
        record.date = form.date.data
        record.session = form.session.data
        record.quantity = float(form.quantity.data)
        record.fat_content = float(form.fat_content.data) if form.fat_content.data else None
        record.protein_content = float(form.protein_content.data) if form.protein_content.data else None
        record.lactose_content = float(form.lactose_content.data) if form.lactose_content.data else None
        record.snf = float(form.snf.data) if form.snf.data else None
        record.density = float(form.density.data) if form.density.data else None
        record.temperature = float(form.temperature.data) if form.temperature.data else None
        record.quality_grade = form.quality_grade.data if form.quality_grade.data else None
        record.price_per_liter = form.price_per_liter.data
        record.notes = form.notes.data
        record.anomalies = form.anomalies.data
        
        # Recalculate total amount
        if record.price_per_liter and record.quantity:
            record.total_amount = float(record.price_per_liter) * float(record.quantity)
        
        db.session.commit()
        
        # Update daily summary
        update_daily_summary(farm_id, old_date)
        if record.date != old_date:
            update_daily_summary(farm_id, record.date)
        
        flash('Milking record updated successfully', 'success')
        return redirect(url_for('milking.list_milking_records'))
    
    return render_template('milking/record_form.html', form=form, farm=farm, record=record)


@milking_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@farm_required
@permission_required('manage_milking')
def delete_milking_record(id):
    """Delete milking record."""
    farm_id = session.get('current_farm_id')
    record = MilkingRecord.query.filter_by(id=id, farm_id=farm_id).first_or_404()
    
    record_date = record.date
    db.session.delete(record)
    db.session.commit()
    
    # Update daily summary
    update_daily_summary(farm_id, record_date)
    
    flash('Milking record deleted successfully', 'success')
    return redirect(url_for('milking.list_milking_records'))


@milking_bp.route('/reports')
@login_required
@farm_required
@permission_required('view_reports')
def milking_reports():
    """Milking production reports and analytics."""
    farm_id = session.get('current_farm_id')
    farm = db.session.get(Farm, farm_id)
    
    # Date range (default: last 30 days)
    date_to = date.today()
    date_from = date_to - timedelta(days=30)
    
    # Get custom date range if provided
    if request.args.get('date_from'):
        date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d').date()
    if request.args.get('date_to'):
        date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d').date()
    
    # Get daily summaries
    summaries = MilkingSummary.query.filter(
        and_(
            MilkingSummary.farm_id == farm_id,
            MilkingSummary.date >= date_from,
            MilkingSummary.date <= date_to
        )
    ).order_by(MilkingSummary.date.desc()).all()
    
    # Calculate overall stats
    total_quantity = sum(s.total_quantity for s in summaries)
    total_revenue = sum(s.total_revenue or 0 for s in summaries)
    avg_per_day = total_quantity / len(summaries) if summaries else 0
    
    # Top producing animals (last 30 days)
    top_animals = db.session.query(
        Animal.id,
        Animal.tag_no,
        Animal.name,
        func.sum(MilkingRecord.quantity).label('total_milk'),
        func.count(MilkingRecord.id).label('milking_count'),
        func.avg(MilkingRecord.quantity).label('avg_per_session')
    ).join(MilkingRecord).filter(
        and_(
            MilkingRecord.farm_id == farm_id,
            MilkingRecord.date >= date_from,
            MilkingRecord.date <= date_to
        )
    ).group_by(Animal.id).order_by(func.sum(MilkingRecord.quantity).desc()).limit(10).all()
    
    # Chart data for last 30 days
    chart_data = {
        'dates': [s.date.strftime('%Y-%m-%d') for s in reversed(summaries)],
        'quantities': [float(s.total_quantity) for s in reversed(summaries)],
        'revenues': [float(s.total_revenue or 0) for s in reversed(summaries)]
    }
    
    stats = {
        'total_quantity': total_quantity,
        'total_revenue': total_revenue,
        'avg_per_day': avg_per_day,
        'days_count': len(summaries),
        'date_from': date_from,
        'date_to': date_to
    }

    session_breakdown = {}
    for record in MilkingRecord.query.filter(
        MilkingRecord.farm_id == farm_id,
        MilkingRecord.date >= date_from,
        MilkingRecord.date <= date_to,
    ).all():
        bucket = session_breakdown.setdefault(record.session, {'quantity': 0, 'count': 0, 'average': 0})
        bucket['quantity'] += record.quantity or 0
        bucket['count'] += 1
    for bucket in session_breakdown.values():
        bucket['average'] = bucket['quantity'] / bucket['count'] if bucket['count'] else 0
    animal_average = total_quantity / len(top_animals) if top_animals else 0
    top_producers = [
        {'id': row.id, 'name': row.name or '', 'tag_number': row.tag_no,
         'total_quantity': float(row.total_milk or 0), 'avg_quantity': float(row.avg_per_session or 0),
         'session_count': row.milking_count, 'avg_quality': 0}
        for row in top_animals
    ]
    daily_summaries = [
        {'date': row.date, 'total_quantity': row.total_quantity or 0,
         'animals_milked': row.total_animals_milked or 0, 'sessions': 0,
         'avg_quality': 0, 'avg_fat_content': row.avg_fat_content or 0,
         'abnormalities_count': 0}
        for row in summaries
    ]
    
    return render_template('milking/reports.html',
                         farm=farm,
                         summaries=summaries,
                         top_animals=top_animals,
                         chart_data=chart_data,
                         stats=stats,
                         report_type=request.args.get('report_type', 'daily'),
                         from_date=date_from,
                         to_date=date_to,
                         total_production=total_quantity,
                         daily_average=avg_per_day,
                         animal_average=animal_average,
                         avg_quality=0,
                         session_breakdown=session_breakdown,
                         top_producers=top_producers,
                         daily_summaries=daily_summaries)


def update_daily_summary(farm_id, summary_date):
    """Update or create daily milking summary for a specific date."""
    # Get all records for this farm and date
    records = MilkingRecord.query.filter_by(farm_id=farm_id, date=summary_date).all()
    
    if not records:
        # No records for this date, delete summary if exists
        summary = MilkingSummary.query.filter_by(farm_id=farm_id, date=summary_date).first()
        if summary:
            db.session.delete(summary)
            db.session.commit()
        return
    
    # Calculate summary data
    total_quantity = sum(r.quantity for r in records)
    unique_animals = len(set(r.animal_id for r in records))
    
    morning_qty = sum(r.quantity for r in records if r.session == 'MORNING')
    afternoon_qty = sum(r.quantity for r in records if r.session == 'AFTERNOON')
    evening_qty = sum(r.quantity for r in records if r.session == 'EVENING')
    
    # Average quality metrics
    fat_records = [r.fat_content for r in records if r.fat_content]
    protein_records = [r.protein_content for r in records if r.protein_content]
    
    avg_fat = sum(fat_records) / len(fat_records) if fat_records else None
    avg_protein = sum(protein_records) / len(protein_records) if protein_records else None
    
    # Total revenue
    total_revenue = sum(r.total_amount for r in records if r.total_amount)
    
    # Get or create summary
    summary = MilkingSummary.query.filter_by(farm_id=farm_id, date=summary_date).first()
    if not summary:
        summary = MilkingSummary(farm_id=farm_id, date=summary_date)
        db.session.add(summary)
    
    # Update summary
    summary.total_animals_milked = unique_animals
    summary.total_quantity = total_quantity
    summary.average_per_animal = total_quantity / unique_animals if unique_animals > 0 else 0
    summary.morning_quantity = morning_qty
    summary.afternoon_quantity = afternoon_qty
    summary.evening_quantity = evening_qty
    summary.avg_fat_content = avg_fat
    summary.avg_protein_content = avg_protein
    summary.total_revenue = total_revenue
    
    db.session.commit()
