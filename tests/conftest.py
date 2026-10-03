import pytest

from app.database.database import Database


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()
