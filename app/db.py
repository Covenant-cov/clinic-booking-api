"""Postgres access. One short-lived connection per request (safe for serverless)."""

from __future__ import annotations

import os
import ssl
from contextlib import contextmanager
from urllib.parse import parse_qs, unquote, urlparse

import pg8000.dbapi

UNIQUE_VIOLATION = "23505"

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS slots (
        id        TEXT PRIMARY KEY,
        provider  TEXT NOT NULL,
        start_raw TEXT NOT NULL,
        end_raw   TEXT NOT NULL,
        start_at  TIMESTAMPTZ NOT NULL,
        end_at    TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bookings (
        seq        BIGSERIAL PRIMARY KEY,
        id         TEXT NOT NULL UNIQUE,
        slot_id    TEXT NOT NULL,
        name       TEXT NOT NULL,
        email      TEXT NOT NULL,
        status     TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    )""",
    # Level 3: the database itself guarantees one confirmed booking per slot,
    # so simultaneous requests can't both succeed.
    """CREATE UNIQUE INDEX IF NOT EXISTS one_confirmed_booking_per_slot
        ON bookings (slot_id) WHERE status = 'confirmed'""",
    "CREATE INDEX IF NOT EXISTS bookings_by_email ON bookings (email, created_at, seq)",
    # Level 4: stored responses for Idempotency-Key replays.
    """CREATE TABLE IF NOT EXISTS idempotency_keys (
        key         TEXT PRIMARY KEY,
        body_hash   TEXT NOT NULL,
        status_code INT NOT NULL,
        response    TEXT NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    # Level 5: booking attempts per email, for rate limiting.
    """CREATE TABLE IF NOT EXISTS booking_attempts (
        id    BIGSERIAL PRIMARY KEY,
        email TEXT NOT NULL,
        at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    )""",
    "CREATE INDEX IF NOT EXISTS attempts_by_email ON booking_attempts (email, at)",
]

_schema_ready = False


def _connect():
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    u = urlparse(url)
    query = parse_qs(u.query)
    needs_ssl = query.get("sslmode", ["require"])[0] != "disable"
    conn = pg8000.dbapi.connect(
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        host=u.hostname,
        port=u.port or 5432,
        database=(u.path or "/postgres").lstrip("/"),
        ssl_context=ssl.create_default_context() if needs_ssl else None,
        timeout=15,
    )
    schema = os.environ.get("DB_SCHEMA")  # only used by the test suite
    if schema:
        cur = conn.cursor()
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        cur.execute(f'SET search_path TO "{schema}"')
        conn.commit()
    return conn


def _ensure_schema(conn) -> None:
    global _schema_ready
    if _schema_ready:
        return
    cur = conn.cursor()
    # Skip the DDL when the schema already exists: even CREATE INDEX IF NOT EXISTS takes a
    # table lock, which can deadlock with bookings running on other instances.
    cur.execute("SELECT to_regclass('attempts_by_email') IS NOT NULL")
    if cur.fetchone()[0]:
        conn.commit()
        _schema_ready = True
        return
    # Serialise first-time setup across instances that cold-start together.
    cur.execute("SELECT pg_advisory_xact_lock(7231001)")
    for statement in SCHEMA_SQL:
        cur.execute(statement)
    conn.commit()
    _schema_ready = True


@contextmanager
def transaction():
    """A connection inside one transaction: committed on success, rolled back on error."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_unique_violation(err: Exception) -> bool:
    detail = err.args[0] if err.args else None
    return isinstance(detail, dict) and detail.get("C") == UNIQUE_VIOLATION
