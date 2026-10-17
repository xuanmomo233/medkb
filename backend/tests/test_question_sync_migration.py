import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base

TABLES = {"sync_cursors", "sync_runs", "sync_documents", "sync_revisions", "sync_proposals", "sync_classification_rules"}


@pytest.mark.asyncio
async def test_sync_migration_roundtrip_preserves_existing_data():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261017_sync_question_ingestion.py"
    spec = importlib.util.spec_from_file_location("sync_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        def check(db):
            Base.metadata.create_all(db, tables=[t for t in Base.metadata.sorted_tables if t.name not in TABLES])
            db.exec_driver_sql("INSERT INTO users(id,username,password_hash,is_admin) VALUES(1,'admin','unused',1)")
            old_names = set(inspect(db).get_table_names())
            with Operations.context(MigrationContext.configure(db)):
                migration.upgrade()
            assert set(inspect(db).get_table_names()) == old_names | TABLES
            for name in TABLES:
                assert set(c["name"] for c in inspect(db).get_columns(name)) == set(Base.metadata.tables[name].columns.keys())
            with Operations.context(MigrationContext.configure(db)):
                migration.downgrade()
            assert set(inspect(db).get_table_names()) == old_names
            assert db.exec_driver_sql("SELECT username FROM users WHERE id=1").scalar() == "admin"
        await conn.run_sync(check)
    await engine.dispose()
