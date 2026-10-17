import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base

NEW_TABLES = {"plan_snapshots", "plan_tasks", "plan_task_sections", "question_merges", "question_relations", "schedule_days"}


@pytest.mark.asyncio
async def test_additive_migration_roundtrip_preserves_existing_tables():
    migrations = []
    for filename in ("20261017_01_plan_queue.py", "20261017_02_schedule_day.py"):
        path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
        spec = importlib.util.spec_from_file_location(filename[:-3], path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migrations.append(migration)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

        def check(db):
            old = [table for table in Base.metadata.sorted_tables if table.name not in NEW_TABLES]
            Base.metadata.create_all(db, tables=old)
            old_names = set(inspect(db).get_table_names())
            with Operations.context(MigrationContext.configure(db)):
                for migration in migrations:
                    migration.upgrade()
            assert set(inspect(db).get_table_names()) == old_names | NEW_TABLES
            for name in NEW_TABLES:
                assert set(c["name"] for c in inspect(db).get_columns(name)) == set(Base.metadata.tables[name].columns.keys())
                assert db.exec_driver_sql(f"SELECT COUNT(*) FROM {name}").scalar() == 0
            with Operations.context(MigrationContext.configure(db)):
                for migration in reversed(migrations):
                    migration.downgrade()
            assert set(inspect(db).get_table_names()) == old_names

        await conn.run_sync(check)
    await engine.dispose()
