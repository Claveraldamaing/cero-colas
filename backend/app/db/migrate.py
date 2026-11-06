"""Versioned, additive initial P1 migration. Never imports or copies legacy data."""
from sqlalchemy import Column, String, DateTime, select, func
from app.core.database import Base, engine


class SchemaMigration(Base):
    __tablename__ = 'p1_schema_migrations'
    version = Column(String(40), primary_key=True)
    applied_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def migrate():
    from app.modules.auth import models as auth_models  # noqa: F401: register metadata
    from app.modules.reservations import models as reservation_models  # noqa: F401: register metadata
    from app.modules.surveys import models as survey_models  # noqa: F401: register metadata
    with engine.begin() as connection:
        if connection.dialect.name == 'postgresql':
            # Concurrent application starts cannot apply the same migration twice.
            from sqlalchemy import text
            connection.execute(text('SELECT pg_advisory_xact_lock(2086102001)'))
        SchemaMigration.__table__.create(connection, checkfirst=True)
        known = set(connection.execute(select(SchemaMigration.version)).scalars())
        if known - {'001_p1', '002_reservations', '003_reservation_idempotency'}:
            raise RuntimeError('La base tiene una versión más reciente que esta aplicación.')
        if '001_p1' not in known:
            Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables if t.name.startswith('p1_')])
            connection.execute(SchemaMigration.__table__.insert().values(version='001_p1'))
        if '002_reservations' not in known:
            reservation_tables = {'cita_local', 'cita_indicacion', 'auditoria_api'}
            Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables if t.name in reservation_tables])
            connection.execute(SchemaMigration.__table__.insert().values(version='002_reservations'))
        if '003_reservation_idempotency' not in known:
            from sqlalchemy import inspect, text
            columns = {column['name'] for column in inspect(connection).get_columns('cita_local')}
            if 'idempotency_fingerprint' not in columns:
                connection.execute(text('ALTER TABLE cita_local ADD COLUMN idempotency_fingerprint VARCHAR(64)'))
            connection.execute(SchemaMigration.__table__.insert().values(version='003_reservation_idempotency'))


if __name__ == '__main__':
    migrate()
    print('Migraciones de base de datos aplicadas; base lista.')
