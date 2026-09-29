"""Alembic migrations are the schema source of truth and match the ORM models (docs/06 §3)."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from fmpoc.db import upgrade_database
from fmpoc.models import Base


def test_migrations_match_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.sqlite3'}"
    upgrade_database(url)
    eng = create_engine(url)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
    assert "alembic_version" in inspect(eng).get_table_names()


def test_upgrade_is_idempotent_and_preserves_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.sqlite3'}"
    upgrade_database(url)
    eng = create_engine(url)
    with eng.begin() as c:
        c.exec_driver_sql("INSERT INTO workspace (name, created_at, next_entity_number) VALUES ('keep', '2026-01-01', 1)")
    upgrade_database(url)  # re-running on an existing DB never recreates it
    with eng.connect() as c:
        assert c.exec_driver_sql("SELECT name FROM workspace").scalar() == "keep"
