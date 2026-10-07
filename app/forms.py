from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, SelectField, SelectMultipleField,
    TextAreaField, DateField, DecimalField, IntegerField, HiddenField
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError, NumberRange
from app.models import User, Organization


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(1, 80)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    """Form for organization owner signup - creates both user and organization."""
    # Personal information
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(1, 60)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(1, 60)])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

    # Organization information
    organization_name = StringField('Organization/Farm Business Name', validators=[DataRequired(), Length(3, 120)])
    organization_slug = StringField('Organization URL Slug', validators=[DataRequired(), Length(3, 80)])
    country = StringField('Country', validators=[Optional(), Length(0, 60)])
    phone = StringField('Phone', validators=[Optional(), Length(0, 30)])

    submit = SubmitField('Create Account')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_organization_slug(self, field):
        import re
        if not re.match(r'^[a-z0-9-]+$', field.data):
            raise ValidationError('Slug must contain only lowercase letters, numbers, and hyphens.')
        if Organization.query.filter_by(slug=field.data).first():
            raise ValidationError('This organization slug is already taken.')


class StaffRegisterForm(FlaskForm):
    """Create a staff account that waits for an organization owner to assign a farm."""
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(1, 60)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(1, 60)])
    phone = StringField('Phone', validators=[Optional(), Length(0, 30)])
    organization_slug = StringField('Organization Slug', validators=[DataRequired(), Length(3, 80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Create Staff Account')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_organization_slug(self, field):
        organization = Organization.query.filter_by(slug=field.data.strip().lower()).first()
        if not organization or not organization.is_active:
            raise ValidationError('Organization not found. Check the slug with your farm owner.')


class InvitationAcceptForm(FlaskForm):
    """Form for accepting an invitation to join an organization."""
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(1, 60)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(1, 60)])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    phone = StringField('Phone', validators=[Optional(), Length(0, 30)])
    
    submit = SubmitField('Accept Invitation')
    
    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')


class InviteUserForm(FlaskForm):
    """Form for organization owners to invite users to their organization."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    farm_ids = SelectField('Assign to Farms', coerce=int, validators=[Optional()])
    message = TextAreaField('Invitation Message (Optional)', validators=[Optional()])
    
    submit = SubmitField('Send Invitation')
    
    def validate_email(self, field):
        # Check if user already exists in the system
        existing_user = User.query.filter_by(email=field.data).first()
        if existing_user:
            raise ValidationError('A user with this email already exists in the system.')


class AnimalForm(FlaskForm):
    tag_no = StringField('TAG NUMBER (by govt)', validators=[DataRequired(), Length(1, 40)])
    name = StringField('Name', validators=[Optional(), Length(0, 80)])
    gender = SelectField('Gender', choices=[('MALE', 'Male'), ('FEMALE', 'Female'), ('CASTRATED', 'Castrated')], validators=[DataRequired()])
    father_id = SelectField('Male Parent', coerce=int, validators=[Optional()])
    mother_id = SelectField('Female Parent', coerce=int, validators=[Optional()])
    breed_id = SelectField('Breed', coerce=int, validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    color = StringField('Color', validators=[Optional(), Length(0, 60)])
    birth_weight = DecimalField('Birth Weight (kg)', validators=[Optional(), NumberRange(min=0)])
    current_weight = DecimalField('Current Weight (kg)', validators=[Optional(), NumberRange(min=0)])
    purchase_date = DateField('Purchase Date', validators=[Optional()])
    purchase_price = DecimalField('Purchase Price', validators=[Optional(), NumberRange(min=0)])
    feed_id = SelectField('Assigned Feed', coerce=int, validators=[Optional()])
    daily_feed_quantity = DecimalField('Daily Feed Quantity', validators=[Optional(), NumberRange(min=0)])
    source = SelectField('Source', choices=[
        ('BORN_ON_FARM', 'Born on Farm'),
        ('PURCHASED', 'Purchased'),
    ], validators=[DataRequired()])
    location_id = SelectField('Location', coerce=int, validators=[Optional()])
    status = SelectField('Status', choices=[
        ('ACTIVE', 'Active'),
        ('PREGNANT', 'Pregnant'),
        ('SICK', 'Sick'),
        ('QUARANTINE', 'Quarantine'),
        ('SOLD', 'Sold'),
        ('DEAD', 'Dead'),
        ('CULLED', 'Culled'),
    ], validators=[DataRequired()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Animal')


class LocationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(1, 100)])
    capacity = IntegerField('Capacity', validators=[Optional(), NumberRange(min=0)])
    description = StringField('Description', validators=[Optional(), Length(0, 255)])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Location')


class StaffInviteForm(FlaskForm):
    username = StringField('Username (existing user)', validators=[DataRequired()])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    staff_code = StringField('Staff Code', validators=[Optional(), Length(0, 40)])
    designation = StringField('Designation', validators=[Optional(), Length(0, 80)])
    joining_date = DateField('Joining Date', validators=[Optional()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Add Staff Member')


class BreedingForm(FlaskForm):
    female_animal_id = SelectField('Female Animal', coerce=int, validators=[DataRequired()])
    male_animal_id = SelectField('Male Animal', coerce=int, validators=[Optional()])
    heat_date = DateField('Heat Date', validators=[Optional()])
    mating_date = DateField('Mating Date', validators=[Optional()])
    mating_method = SelectField('Method', choices=[
        ('NATURAL', 'Natural'),
        ('AI', 'Artificial Insemination'),
    ], validators=[Optional()])
    expected_delivery_date = DateField('Expected Delivery', validators=[Optional()])
    pregnancy_status = SelectField('Pregnancy Status', choices=[
        ('UNKNOWN', 'Unknown'),
        ('CONFIRMED', 'Confirmed'),
        ('NOT_PREGNANT', 'Not Pregnant'),
        ('DELIVERED', 'Delivered'),
        ('ABORTED', 'Aborted'),
    ], validators=[DataRequired()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Breeding Record')


class VaccinationForm(FlaskForm):
    animal_id = SelectField('Animal', coerce=int, validators=[DataRequired()])
    vaccine = SelectField('Vaccine', choices=[
        ('FMD', 'Cattle: FMD'),
        ('LSD', 'Cattle: LSD'),
        ('HS', 'Cattle/Goat: HS'),
        ('BQ', 'Cattle: BQ'),
        ('ANTHRAX', 'Cattle: Anthrax'),
        ('PPR', 'Goat: PPR'),
        ('GOAT_POX', 'Goat: Goat Pox'),
        ('ENTEROTOXEMIA', 'Goat: Enterotoxemia'),
    ], validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    dose = StringField('Dose', validators=[Optional(), Length(0, 40)])
    batch_no = StringField('Batch No', validators=[Optional(), Length(0, 60)])
    next_due_date = DateField('Next Due Date', validators=[Optional()])
    cost = DecimalField('Cost', validators=[Optional(), NumberRange(min=0)])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Vaccination')


class TreatmentForm(FlaskForm):
    animal_id = SelectField('Animal', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    symptoms = TextAreaField('Symptoms', validators=[Optional()])
    diagnosis = TextAreaField('Diagnosis', validators=[Optional()])
    medicine = SelectField('Medicine', choices=[
        ('', 'Select medicine'),
        ('DEWORMING', 'Deworming'),
        ('CALCIUM_VITAMIN', 'Calcium and Vitamin'),
        ('GENERAL_MEDICINE', 'General Medicine'),
    ], validators=[Optional()])
    dose = StringField('Dose', validators=[Optional(), Length(0, 40)])
    follow_up_date = DateField('Follow-up Date', validators=[Optional()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Treatment')


class FeedForm(FlaskForm):
    feed_name = StringField('Feed Name', validators=[DataRequired(), Length(1, 100)])
    unit = SelectField('Unit', choices=[('KG', 'Kg'), ('BAG', 'Bag'), ('LITRE', 'Litre')], validators=[DataRequired()])
    purchase_price = DecimalField('Purchase Price', validators=[Optional(), NumberRange(min=0)])
    stock_quantity = DecimalField('Stock Quantity', validators=[Optional(), NumberRange(min=0)], default=0)
    minimum_stock = DecimalField('Minimum Stock', validators=[Optional(), NumberRange(min=0)], default=0)
    expiry_date = DateField('Expiry Date', validators=[Optional()])
    submit = SubmitField('Save Feed')


class FeedConsumptionForm(FlaskForm):
    feed_id = SelectField('Feed', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    quantity = DecimalField('Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    animal_category = SelectField('Animal Category', choices=[
        ('ALL', 'All'), ('KIDS', 'Kids'), ('FEMALE', 'Female'), ('MALE', 'Male')
    ], validators=[DataRequired()])
    number_of_animals = IntegerField('Number of Animals', validators=[Optional(), NumberRange(min=0)])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Record Consumption')


class ExpenseForm(FlaskForm):
    expense_date = DateField('Date', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('FEED', 'Feed'), ('MEDICINE', 'Medicine'), ('VACCINE', 'Vaccine'),
        ('LABOUR', 'Labour'), ('ELECTRICITY', 'Electricity'), ('TRANSPORT', 'Transport'),
        ('REPAIR', 'Repair'), ('ANIMAL_PURCHASE', 'Animal Purchase'), ('OTHER', 'Other'),
    ], validators=[DataRequired()])
    description = StringField('Description', validators=[Optional(), Length(0, 255)])
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    payment_mode = SelectField('Payment Mode', choices=[
        ('CASH', 'Cash'), ('BANK_TRANSFER', 'Bank Transfer'), ('UPI', 'UPI'), ('OTHER', 'Other')
    ], validators=[DataRequired()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Expense')


class AnimalSaleForm(FlaskForm):
    animal_id = SelectField('Animal', coerce=int, validators=[DataRequired()])
    buyer_id = SelectField('Buyer', coerce=int, validators=[DataRequired()])
    sale_date = DateField('Sale Date', validators=[DataRequired()])
    live_weight = DecimalField('Live Weight (kg)', validators=[Optional(), NumberRange(min=0)])
    rate_per_kg = DecimalField('Rate per Kg', validators=[Optional(), NumberRange(min=0)])
    total_amount = DecimalField('Total Amount', validators=[Optional(), NumberRange(min=0)])
    payment_mode = SelectField('Payment Mode', choices=[
        ('CASH', 'Cash'), ('BANK_TRANSFER', 'Bank Transfer'), ('UPI', 'UPI'), ('OTHER', 'Other')
    ], validators=[DataRequired()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Record Sale')


class CustomerForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(1, 120)])
    phone = StringField('Phone', validators=[Optional(), Length(0, 30)])
    address = TextAreaField('Address', validators=[Optional()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Customer')


class FarmForm(FlaskForm):
    name = StringField('Farm Name', validators=[DataRequired(), Length(1, 120)])
    code = StringField('Farm Code', validators=[DataRequired(), Length(1, 40)])
    address = TextAreaField('Address', validators=[Optional()])
    contact_phone = StringField('Contact Phone', validators=[Optional(), Length(0, 30)])
    status = SelectField('Status', choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive')], validators=[DataRequired()])
    submit = SubmitField('Save Farm')


class RoleForm(FlaskForm):
    code = StringField('Role Code', validators=[DataRequired(), Length(2, 40)])
    name = StringField('Role Name', validators=[DataRequired(), Length(2, 80)])
    description = TextAreaField('Description', validators=[Optional()])
    permission_ids = SelectMultipleField('Allowed Pages and Actions', coerce=int, validators=[Optional()])
    submit = SubmitField('Save Role')


class OrganizationProfileForm(FlaskForm):
    """Form for editing organization profile information."""
    name = StringField('Organization Name', validators=[DataRequired(), Length(3, 120)])
    slug = StringField('Organization Slug', validators=[DataRequired(), Length(3, 80)])
    contact_email = StringField('Contact Email', validators=[Optional(), Email()])
    contact_phone = StringField('Contact Phone', validators=[Optional(), Length(0, 30)])
    address = TextAreaField('Address', validators=[Optional()])
    submit = SubmitField('Update Profile')
    
    def __init__(self, original_slug=None, *args, **kwargs):
        super(OrganizationProfileForm, self).__init__(*args, **kwargs)
        self.original_slug = original_slug
    
    def validate_slug(self, field):
        # Only validate if slug has changed
        if field.data != self.original_slug:
            import re
            if not re.match(r'^[a-z0-9-]+$', field.data):
                raise ValidationError('Slug must contain only lowercase letters, numbers, and hyphens.')
            if Organization.query.filter_by(slug=field.data).first():
                raise ValidationError('This organization slug is already taken.')


class SubscriptionPlanForm(FlaskForm):
    """Form for platform admins to create/edit subscription plans."""
    name = StringField('Plan Name', validators=[DataRequired(), Length(3, 60)])
    description = TextAreaField('Description', validators=[Optional()])
    price_amount = DecimalField('Price', validators=[DataRequired(), NumberRange(min=0)])
    price_currency = SelectField('Currency', choices=[
        ('USD', 'USD'), ('EUR', 'EUR'), ('GBP', 'GBP'), ('INR', 'INR')
    ], default='USD', validators=[DataRequired()])
    billing_period = SelectField('Billing Period', choices=[
        ('month', 'Monthly'), ('year', 'Yearly')
    ], default='month', validators=[DataRequired()])
    
    max_farms = IntegerField('Max Farms', validators=[DataRequired(), NumberRange(min=1)])
    max_animals = IntegerField('Max Animals', validators=[DataRequired(), NumberRange(min=1)])
    max_staff = IntegerField('Max Staff', validators=[DataRequired(), NumberRange(min=1)])
    storage_limit_gb = IntegerField('Storage Limit (GB)', validators=[DataRequired(), NumberRange(min=1)])
    
    features = TextAreaField('Features (comma-separated)', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    is_popular = BooleanField('Mark as Popular', default=False)
    
    submit = SubmitField('Save Plan')


# =============================================================================
# MILKING MODULE FORMS
# =============================================================================

class MilkingRecordForm(FlaskForm):
    """Form to record milk production."""
    animal_id = SelectField('Animal', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    session = SelectField('Session', choices=[
        ('MORNING', 'Morning'),
        ('AFTERNOON', 'Afternoon'),
        ('EVENING', 'Evening')
    ], validators=[DataRequired()])
    quantity = DecimalField('Quantity (Liters)', places=2, validators=[DataRequired(), NumberRange(min=0)])
    
    # Quality metrics (optional)
    fat_content = DecimalField('Fat Content (%)', places=2, validators=[Optional(), NumberRange(min=0, max=100)])
    protein_content = DecimalField('Protein Content (%)', places=2, validators=[Optional(), NumberRange(min=0, max=100)])
    lactose_content = DecimalField('Lactose Content (%)', places=2, validators=[Optional(), NumberRange(min=0, max=100)])
    snf = DecimalField('SNF (%)', places=2, validators=[Optional(), NumberRange(min=0, max=100)])
    density = DecimalField('Density (g/ml)', places=3, validators=[Optional(), NumberRange(min=0)])
    temperature = DecimalField('Temperature (°C)', places=1, validators=[Optional(), NumberRange(min=0, max=50)])
    
    # Quality grade
    quality_grade = SelectField('Quality Grade', choices=[
        ('', 'Not Graded'),
        ('A+', 'A+ (Premium)'),
        ('A', 'A (Excellent)'),
        ('B', 'B (Good)'),
        ('C', 'C (Average)'),
        ('REJECT', 'Reject')
    ], validators=[Optional()])
    
    # Commercial
    price_per_liter = DecimalField('Price per Liter', places=2, validators=[Optional(), NumberRange(min=0)])
    
    # Notes
    notes = TextAreaField('Notes', validators=[Optional()])
    anomalies = TextAreaField('Anomalies (blood, unusual color, etc.)', validators=[Optional()])
    
    submit = SubmitField('Record Milk Production')


class MilkingFilterForm(FlaskForm):
    """Form to filter milking records."""
    animal_id = SelectField('Animal', coerce=int, validators=[Optional()])
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    session = SelectField('Session', choices=[
        ('', 'All Sessions'),
        ('MORNING', 'Morning'),
        ('AFTERNOON', 'Afternoon'),
        ('EVENING', 'Evening')
    ], validators=[Optional()])
    quality_grade = SelectField('Quality Grade', choices=[
        ('', 'All Grades'),
        ('A+', 'A+'),
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('REJECT', 'Reject')
    ], validators=[Optional()])
    submit = SubmitField('Filter')


# =============================================================================
# ENHANCED TREATMENT FORMS
# =============================================================================

class EnhancedTreatmentForm(FlaskForm):
    """Enhanced treatment form with categories and medication templates."""
    animal_id = SelectField('Animal', coerce=int, validators=[DataRequired()])
    category_id = SelectField('Treatment Category', coerce=int, validators=[DataRequired()])
    date = DateField('Treatment Date', validators=[DataRequired()])
    
    # Medication
    medication_template_id = SelectField('Medication Template', coerce=int, validators=[Optional()])
    medicine = StringField('Medication Name', validators=[Optional(), Length(0, 120)])
    
    # Dosage
    dose = StringField('Dosage', validators=[Optional(), Length(0, 40)])
    dosage_unit = SelectField('Dosage Unit', choices=[
        ('', 'Select Unit'),
        ('ml', 'Milliliters (ml)'),
        ('mg', 'Milligrams (mg)'),
        ('g', 'Grams (g)'),
        ('tablets', 'Tablets'),
        ('capsules', 'Capsules'),
        ('drops', 'Drops'),
        ('cc', 'Cubic Centimeters (cc)')
    ], validators=[Optional()])
    
    administration_route = SelectField('Administration Route', choices=[
        ('', 'Select Route'),
        ('ORAL', 'Oral'),
        ('INJECTION_IM', 'Injection - Intramuscular'),
        ('INJECTION_IV', 'Injection - Intravenous'),
        ('INJECTION_SC', 'Injection - Subcutaneous'),
        ('TOPICAL', 'Topical'),
        ('DRENCH', 'Drench'),
        ('FEED', 'Mixed in Feed'),
        ('WATER', 'Mixed in Water')
    ], validators=[Optional()])
    
    # Schedule
    frequency = SelectField('Frequency', choices=[
        ('ONCE', 'One-time treatment'),
        ('DAILY', 'Once daily'),
        ('TWICE_DAILY', 'Twice daily'),
        ('THREE_TIMES_DAILY', 'Three times daily'),
        ('WEEKLY', 'Once weekly'),
        ('BIWEEKLY', 'Every two weeks'),
        ('MONTHLY', 'Once monthly')
    ], validators=[Optional()])
    
    duration_days = IntegerField('Duration (days)', validators=[Optional(), NumberRange(min=1)])
    next_dose_date = DateField('Next Dose Date', validators=[Optional()])
    
    # Clinical info
    symptoms = TextAreaField('Symptoms', validators=[Optional()])
    diagnosis = TextAreaField('Diagnosis', validators=[Optional()])
    
    # Personnel
    vet = SelectField('Veterinarian', coerce=int, validators=[Optional()])
    follow_up_date = DateField('Follow-up Date', validators=[Optional()])
    
    # Cost
    cost = DecimalField('Treatment Cost', places=2, validators=[Optional(), NumberRange(min=0)])
    
    # Withdrawal period for food animals
    withdrawal_period_days = IntegerField('Withdrawal Period (days)', validators=[Optional(), NumberRange(min=0)])
    
    # Notes
    remarks = TextAreaField('Remarks', validators=[Optional()])
    
    submit = SubmitField('Record Treatment')


class MedicationTemplateForm(FlaskForm):
    """Form to create/edit medication templates."""
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    name = StringField('Medication Name', validators=[DataRequired(), Length(1, 200)])
    generic_name = StringField('Generic Name', validators=[Optional(), Length(0, 200)])
    manufacturer = StringField('Manufacturer', validators=[Optional(), Length(0, 200)])
    
    # Dosage
    default_dosage = StringField('Default Dosage', validators=[Optional(), Length(0, 100)])
    dosage_unit = SelectField('Dosage Unit', choices=[
        ('ml', 'ml'),
        ('mg', 'mg'),
        ('g', 'g'),
        ('tablets', 'tablets'),
        ('capsules', 'capsules')
    ], validators=[Optional()])
    
    calculate_by_weight = BooleanField('Calculate dosage by animal weight')
    dosage_per_kg = DecimalField('Dosage per kg', places=2, validators=[Optional(), NumberRange(min=0)])
    
    # Administration
    administration_route = SelectField('Administration Route', choices=[
        ('ORAL', 'Oral'),
        ('INJECTION', 'Injection'),
        ('TOPICAL', 'Topical'),
        ('IV', 'Intravenous')
    ], validators=[Optional()])
    
    frequency = StringField('Frequency', validators=[Optional(), Length(0, 100)])
    default_duration_days = IntegerField('Default Duration (days)', validators=[Optional(), NumberRange(min=1)])
    
    # Medical info
    indications = TextAreaField('Indications', validators=[Optional()])
    contraindications = TextAreaField('Contraindications', validators=[Optional()])
    side_effects = TextAreaField('Side Effects', validators=[Optional()])
    
    # Withdrawal
    withdrawal_period_days = IntegerField('Withdrawal Period (days)', validators=[Optional(), NumberRange(min=0)])
    
    # Status
    is_active = BooleanField('Active', default=True)
    requires_prescription = BooleanField('Requires Prescription')
    
    submit = SubmitField('Save Medication Template')


# =============================================================================
# FEED CONSUMPTION FORM
# =============================================================================

class AnimalFeedConsumptionForm(FlaskForm):
    """Form to record feed consumption for individual animals."""
    animal_id = SelectField('Animal', coerce=int, validators=[DataRequired()])
    feed_id = SelectField('Feed Type', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    quantity = DecimalField('Quantity (kg)', places=2, validators=[DataRequired(), NumberRange(min=0)])
    
    feeding_time = SelectField('Feeding Time', choices=[
        ('MORNING', 'Morning'),
        ('NOON', 'Noon'),
        ('EVENING', 'Evening'),
        ('NIGHT', 'Night')
    ], validators=[Optional()])
    
    feeding_method = SelectField('Feeding Method', choices=[
        ('MANUAL', 'Manual Feeding'),
        ('AUTO_FEEDER', 'Automatic Feeder'),
        ('GRAZING', 'Grazing'),
        ('TMR', 'Total Mixed Ration')
    ], validators=[Optional()])
    
    notes = TextAreaField('Notes', validators=[Optional()])
    
    submit = SubmitField('Record Feed Consumption')
