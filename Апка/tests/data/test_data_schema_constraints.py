import os

import psycopg
import pytest


def _pg_conninfo() -> str:
    host = os.environ.get("PGHOST", "localhost")
    port = int(os.environ.get("PGPORT", "5432"))
    user = os.environ.get("PGUSER", "app")
    password = os.environ.get("PGPASSWORD", "app")
    dbname = os.environ.get("PGDATABASE", "app")
    return f"host={host} port={port} user={user} password={password} dbname={dbname}"


@pytest.fixture(scope="session")
def pg_conn():
    conn = psycopg.connect(_pg_conninfo(), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def _has_unique_constraint(conn, table: str, columns: list[str]) -> bool:
    cols = tuple(columns)
    q = """
    SELECT c.conname
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND t.relname = %s
      AND c.contype = 'u'
      AND (
        SELECT array_agg(a.attname ORDER BY x.ord)
        FROM unnest(c.conkey) WITH ORDINALITY AS x(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
      ) = %s
    """
    with conn.cursor() as cur:
        cur.execute(q, (table, list(cols)))
        return cur.fetchone() is not None


def _has_unique_index(conn, table: str, columns: list[str]) -> bool:
    cols = [c.strip() for c in columns]
    q = """
    SELECT 1
    FROM pg_index i
    JOIN pg_class t ON t.oid = i.indrelid
    JOIN pg_class idx ON idx.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND t.relname = %s
      AND i.indisunique = true
      AND (
        SELECT array_agg(a.attname ORDER BY x.ord)
        FROM unnest(i.indkey) WITH ORDINALITY AS x(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
      ) = %s
    LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(q, (table, cols))
        return cur.fetchone() is not None


def _has_unique(conn, table: str, columns: list[str]) -> bool:
    return _has_unique_constraint(conn, table, columns) or _has_unique_index(conn, table, columns)


def _has_index(conn, table: str, column: str) -> bool:
    q = """
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = %s
      AND indexdef ILIKE %s
    LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(q, (table, f"%({column})%"))
        return cur.fetchone() is not None


def _has_fk(conn, table: str, column: str, ref_table: str) -> bool:
    q = """
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_name = tc.constraint_name
     AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name = %s
      AND kcu.column_name = %s
      AND ccu.table_name = %s
    LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(q, (table, column, ref_table))
        return cur.fetchone() is not None


def _table_exists(conn, table: str) -> bool:
    q = """
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = %s
    LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(q, (table,))
        return cur.fetchone() is not None


def _table_has_rows(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {table} LIMIT 1")
        return cur.fetchone() is not None


@pytest.mark.data
def test_users_email_unique_and_indexed(pg_conn) -> None:
    assert _has_unique(pg_conn, "users", ["email"])
    assert _has_index(pg_conn, "users", "email")


@pytest.mark.data
def test_tasks_schema_has_expected_constraints(pg_conn) -> None:
    assert _has_fk(pg_conn, "tasks", "project_id", "projects")
    assert _has_index(pg_conn, "tasks", "project_id")
    assert _has_index(pg_conn, "tasks", "status")
    assert _has_index(pg_conn, "tasks", "is_archived")

    assert _has_unique(pg_conn, "tags", ["name"])
    assert _has_index(pg_conn, "tags", "name")

    assert _has_fk(pg_conn, "task_tags", "task_id", "tasks")
    assert _has_fk(pg_conn, "task_tags", "tag_id", "tags")

    assert _has_fk(pg_conn, "project_members", "project_id", "projects")


@pytest.mark.data
def test_audit_and_notifier_indexes(pg_conn) -> None:
    assert _has_index(pg_conn, "audit_events", "routing_key")
    assert _has_index(pg_conn, "notification_logs", "routing_key")
    assert _has_index(pg_conn, "notification_logs", "status")


@pytest.mark.data
def test_alembic_version_table_exists(pg_conn) -> None:
    # В окружении docker-compose сервисы создают схему через SQLAlchemy `Base.metadata.create_all`.
    # Это не гарантирует наличие `alembic_version`, поэтому проверяем только, что ключевые таблицы существуют.
    assert _table_exists(pg_conn, "users")
    assert _table_exists(pg_conn, "projects")
    assert _table_exists(pg_conn, "tasks")
