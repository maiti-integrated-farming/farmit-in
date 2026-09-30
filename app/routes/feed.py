from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Feed, FeedConsumption
from app.forms import FeedForm, FeedConsumptionForm
from app.decorators import farm_required, permission_required
from decimal import Decimal

feed_bp = Blueprint('feed', __name__)


@feed_bp.route('/')
@login_required
@farm_required
@permission_required('view_feed')
def list_feeds():
    farm_id = session['current_farm_id']
    feeds = Feed.query.filter_by(farm_id=farm_id).order_by(Feed.feed_name).all()
    return render_template('feed/list.html', feeds=feeds)


@feed_bp.route('/add', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_feed')
def add_feed():
    farm_id = session['current_farm_id']
    form = FeedForm()
    if form.validate_on_submit():
        exists = Feed.query.filter_by(farm_id=farm_id, feed_name=form.feed_name.data).first()
        if exists:
            flash('Feed with this name already exists.', 'danger')
            return render_template('feed/form.html', form=form, title='Add Feed')
        feed = Feed(
            farm_id=farm_id,
            feed_name=form.feed_name.data,
            unit=form.unit.data,
            purchase_price=form.purchase_price.data,
            stock_quantity=form.stock_quantity.data or 0,
            minimum_stock=form.minimum_stock.data or 0,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(feed)
        db.session.commit()
        flash('Feed added.', 'success')
        return redirect(url_for('feed.list_feeds'))
    return render_template('feed/form.html', form=form, title='Add Feed')


@feed_bp.route('/consume', methods=['GET', 'POST'])
@login_required
@farm_required
@permission_required('manage_feed')
def consume_feed():
    farm_id = session['current_farm_id']
    form = FeedConsumptionForm()
    form.feed_id.choices = [(f.id, f'{f.feed_name} (Stock: {f.stock_quantity} {f.unit})')
                            for f in Feed.query.filter_by(farm_id=farm_id).all()]
    if form.validate_on_submit():
        feed = db.session.get(Feed, form.feed_id.data)
        if not feed or feed.farm_id != farm_id:
            flash('Invalid feed.', 'danger')
            return redirect(url_for('feed.list_feeds'))
        qty = form.quantity.data
        if feed.stock_quantity < qty:
            flash(f'Insufficient stock. Available: {feed.stock_quantity}', 'danger')
            return render_template('feed/consume_form.html', form=form, title='Record Consumption')
        cost = None
        if feed.purchase_price:
            cost = Decimal(str(feed.purchase_price)) * qty
        rec = FeedConsumption(
            farm_id=farm_id,
            feed_id=feed.id,
            date=form.date.data,
            quantity=qty,
            animal_category=form.animal_category.data,
            number_of_animals=form.number_of_animals.data,
            cost=cost,
            remarks=form.remarks.data,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        feed.stock_quantity = Decimal(str(feed.stock_quantity)) - qty
        db.session.add(rec)
        db.session.commit()
        flash('Consumption recorded and stock updated.', 'success')
        return redirect(url_for('feed.list_feeds'))
    return render_template('feed/consume_form.html', form=form, title='Record Consumption')
