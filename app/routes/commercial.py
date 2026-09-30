from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Expense, Customer, AnimalSale, Animal
from app.forms import ExpenseForm, CustomerForm, AnimalSaleForm
from app.decorators import farm_required, permission_required
from decimal import Decimal

commercial_bp = Blueprint('commercial', __name__)


@commercial_bp.route('/expenses')
@login_required
@farm_required
@permission_required('view_expenses')
def list_expenses():
    farm_id = session['current_farm_id']
    expenses = Expense.query.filter_by(farm_id=farm_id).order_by(Expense.expense_date.desc()).limit(100).all()
    return render_template('commercial/expenses.html', expenses=expenses)


@commercial_bp.route('/expenses/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_expenses')
def add_expense():
    farm_id = session['current_farm_id']
    form = ExpenseForm()
    if form.validate_on_submit():
        exp = Expense(
            farm_id=farm_id,
            expense_date=form.expense_date.data,
            category=form.category.data,
            description=form.description.data,
            amount=form.amount.data,
            payment_mode=form.payment_mode.data,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(exp)
        db.session.commit()
        flash('Expense recorded.', 'success')
        return redirect(url_for('commercial.list_expenses'))
    return render_template('commercial/expense_form.html', form=form, title='Add Expense')


@commercial_bp.route('/customers')
@login_required
@farm_required
@permission_required('view_sales')
def list_customers():
    farm_id = session['current_farm_id']
    customers = Customer.query.filter_by(farm_id=farm_id).order_by(Customer.name).all()
    return render_template('commercial/customers.html', customers=customers)


@commercial_bp.route('/customers/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_sales')
def add_customer():
    farm_id = session['current_farm_id']
    form = CustomerForm()
    if form.validate_on_submit():
        c = Customer(
            farm_id=farm_id,
            name=form.name.data,
            phone=form.phone.data,
            address=form.address.data,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(c)
        db.session.commit()
        flash('Customer added.', 'success')
        return redirect(url_for('commercial.list_customers'))
    return render_template('commercial/customer_form.html', form=form, title='Add Customer')


@commercial_bp.route('/sales')
@login_required
@farm_required
@permission_required('view_sales')
def list_sales():
    farm_id = session['current_farm_id']
    sales = AnimalSale.query.filter_by(farm_id=farm_id).order_by(AnimalSale.sale_date.desc()).all()
    return render_template('commercial/sales.html', sales=sales)


@commercial_bp.route('/sales/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_sales')
def add_sale():
    farm_id = session['current_farm_id']
    form = AnimalSaleForm()
    animals = Animal.query.filter_by(farm_id=farm_id).filter(
        Animal.status.in_(['ACTIVE', 'PREGNANT', 'SICK'])
    ).order_by(Animal.tag_no).all()
    customers = Customer.query.filter_by(farm_id=farm_id).order_by(Customer.name).all()
    form.animal_id.choices = [(a.id, f'{a.tag_no} - {a.name or ""}') for a in animals]
    form.buyer_id.choices = [(c.id, c.name) for c in customers]
    if form.validate_on_submit():
        total = form.total_amount.data
        if form.live_weight.data and form.rate_per_kg.data and not total:
            total = Decimal(str(form.live_weight.data)) * Decimal(str(form.rate_per_kg.data))
        sale = AnimalSale(
            farm_id=farm_id,
            animal_id=form.animal_id.data,
            buyer_id=form.buyer_id.data,
            sale_date=form.sale_date.data,
            live_weight=form.live_weight.data,
            rate_per_kg=form.rate_per_kg.data,
            total_amount=total,
            payment_mode=form.payment_mode.data,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        animal = db.session.get(Animal, form.animal_id.data)
        if animal:
            animal.status = 'SOLD'
        db.session.add(sale)
        db.session.commit()
        flash('Sale recorded. Animal status set to SOLD.', 'success')
        return redirect(url_for('commercial.list_sales'))
    return render_template('commercial/sale_form.html', form=form, title='Record Animal Sale')
