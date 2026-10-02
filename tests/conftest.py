import pytest
from flask import Flask

from app import create_app
from app.models import db


@pytest.fixture()
def app():
    application = create_app('testing')
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SECRET_KEY='pytest-secret')
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
