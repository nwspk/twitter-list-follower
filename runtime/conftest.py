from app import app
from pytest import fixture
from chalice.test import Client


@fixture(scope='function')
def test_client():
    with Client(app) as client:
        yield client
