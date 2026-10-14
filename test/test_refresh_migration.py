from importlib import import_module
from io import StringIO

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect


def test_refresh_migration_upgrade_and_downgrade(monkeypatch):
    migration = import_module("migrations.versions.c87e20a4bd61_add_refresh_tokens")
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            metadata = MetaData()
            Table("user", metadata, Column("id", Integer, primary_key=True))
            metadata.create_all(connection)
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            inspector = inspect(connection)
            assert set(inspector.get_table_names()) == {"user", "refresh_session", "refresh_token"}
            assert inspector.get_foreign_keys("refresh_session")[0]["options"]["ondelete"] == "CASCADE"
            assert inspector.get_foreign_keys("refresh_token")[0]["options"]["ondelete"] == "CASCADE"
            assert {index["name"] for index in inspector.get_indexes("refresh_session")} == {
                "ix_refresh_session_user_id", "ix_refresh_session_expires_at",
            }
            migration.downgrade()
            assert inspect(connection).get_table_names() == ["user"]
    finally:
        engine.dispose()


def test_refresh_migration_generates_mysql_sql_without_connecting(monkeypatch):
    migration = import_module("migrations.versions.c87e20a4bd61_add_refresh_tokens")
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE refresh_session" in sql
    assert "CREATE TABLE refresh_token" in sql
    assert "token_hash VARCHAR(64)" in sql
    assert sql.count("ON DELETE CASCADE") == 2
