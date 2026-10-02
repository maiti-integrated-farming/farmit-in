from io import BytesIO
from datetime import date

from flask import Blueprint, abort, request, send_file, session
from flask_login import current_user, login_required
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph

from app.decorators import farm_required, permission_required
from app.models import (
    Animal, AnimalFeedConsumption, BreedingRecord, Customer, Expense, Feed,
    FeedConsumption, MilkingRecord, StaffMembership, Treatment, Vaccination, db,
)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


SECTION_CONFIG = {
    'animals': ('Animals', Animal, ('tag_no', 'name', 'gender', 'status', 'current_weight')),
    'feed': ('Feed Inventory', Feed, ('feed_name', 'unit', 'stock_quantity', 'minimum_stock', 'purchase_price')),
    'feed-consumption': ('Feed Consumption', FeedConsumption, ('date', 'feed_id', 'quantity', 'animal_category', 'number_of_animals')),
    'animal-feed': ('Animal Feed Consumption', AnimalFeedConsumption, ('date', 'animal_id', 'feed_id', 'quantity', 'unit')),
    'vaccinations': ('Vaccinations', Vaccination, ('date', 'animal_id', 'vaccine', 'dose', 'next_due_date')),
    'treatments': ('Treatments', Treatment, ('date', 'animal_id', 'treatment_type', 'medicine', 'dose', 'follow_up_date')),
    'milking': ('Milking Records', MilkingRecord, ('date', 'animal_id', 'session', 'quantity', 'quality_grade', 'total_amount')),
    'breeding': ('Breeding Records', BreedingRecord, ('mating_date', 'female_animal_id', 'male_animal_id', 'pregnancy_status')),
    'expenses': ('Expenses', Expense, ('expense_date', 'category', 'description', 'amount', 'payment_mode')),
    'customers': ('Customers', Customer, ('name', 'phone', 'address')),
    'staff': ('Staff', StaffMembership, ('user_id', 'farm_id', 'role_id', 'designation', 'joining_date', 'is_active')),
}


def _rows_for_section(section, farm_id):
    config = SECTION_CONFIG.get(section)
    if not config:
        abort(404)
    title, model, fields = config
    query = model.query.filter_by(farm_id=farm_id)
    date_field = getattr(model, 'date', None)
    if date_field is None:
        date_field = getattr(model, 'expense_date', None)
    if date_field is None:
        date_field = getattr(model, 'mating_date', None)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_field and date_from:
        query = query.filter(date_field >= date.fromisoformat(date_from))
    if date_field and date_to:
        query = query.filter(date_field <= date.fromisoformat(date_to))
    records = query.order_by(model.id.desc()).limit(5000).all()
    rows = [[field.replace('_', ' ').title() for field in fields]]
    for record in records:
        values = []
        for field in fields:
            value = getattr(record, field, '')
            if field == 'animal_id' and getattr(record, 'animal', None):
                value = record.animal.tag_no
            values.append('' if value is None else str(value))
        rows.append(values)
    return title, rows


@reports_bp.route('/<section>/<file_format>')
@login_required
@farm_required
@permission_required('view_reports')
def export_report(section, file_format):
    if file_format not in {'xlsx', 'pdf'}:
        abort(404)
    title, rows = _rows_for_section(section, session['current_farm_id'])
    if file_format == 'xlsx':
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = title[:31]
        for row in rows:
            sheet.append(row)
        for cell in sheet[1]:
            cell.font = cell.font.copy(bold=True)
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f'{section}-report.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(letter), rightMargin=24, leftMargin=24)
    styles = getSampleStyleSheet()
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d6a4f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    document.build([Paragraph(title, styles['Title']), table])
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'{section}-report.pdf',
                     mimetype='application/pdf')
