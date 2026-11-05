"""Select --postgres to run the same behaviors against temporary PostgreSQL schemas."""
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from app.core.config import settings


def pytest_addoption(parser):
    parser.addoption('--postgres', action='store_true', help='Use PostgreSQL with isolated temporary schemas, never public tables')


@pytest.fixture
def isolated_engine(request):
    if not request.config.getoption('--postgres'):
        engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        yield engine
        engine.dispose()
        return
    if not settings.DATABASE_URL.startswith('postgresql'):
        pytest.fail('--postgres requires DATABASE_URL pointing to PostgreSQL')
    schema = 'p1_test_' + uuid.uuid4().hex
    admin = create_engine(settings.DATABASE_URL)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(settings.DATABASE_URL, connect_args={'options': f'-csearch_path={schema}'})
    try:
        yield engine
    finally:
        engine.dispose()
        # Only this fixture's randomly generated schema is dropped.
        assert schema.startswith('p1_test_') and len(schema) == 40
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
