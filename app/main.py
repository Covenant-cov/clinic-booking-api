"""Clinic booking API (Koya Cohort 4, Task 1).

Routes live under /api. The booking web page is served at /.
Every API route needs the X-API-Key header.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db
from .page import render_page

RATE_LIMIT = 5          # booking attempts...
RATE_WINDOW_SECONDS = 60  # ...per email per minute
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

app = FastAPI(title="Clinic booking API", docs_url=None, redoc_url=None, openapi_url=None)


class ApiError(Exception):
    def __init__(self, status: int, message: str, headers: dict | None = None):
        self.status, self.message, self.headers = status, message, headers or {}


def error(status: int, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status, headers=headers)


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return error(exc.status, exc.message, exc.headers)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException):
    messages = {404: "not found", 405: "method not allowed"}
    return error(exc.status_code, messages.get(exc.status_code, str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    return error(400, "invalid request")


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception):
    logging.exception("unhandled error")  # full detail goes to the server log only
    return error(500, "internal error")


# ---------- auth (level 2) ----------

def api_key() -> str:
    # Strip stray whitespace or a byte-order mark picked up when the secret was set.
    return os.environ.get("API_KEY", "").strip().lstrip("﻿")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if request.url.path.startswith("/api"):
        expected = api_key()
        given = request.headers.get("x-api-key", "")
        if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
            return error(401, "missing or invalid API key")
    return await call_next(request)


# ---------- helpers ----------

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_time(value) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def booking_json(row) -> dict:
    booking_id, slot_id, name, email, status, created_at = row
    return {"id": booking_id, "slot_id": slot_id, "name": name, "email": email,
            "status": status, "created_at": iso(created_at)}


BOOKING_COLUMNS = "id, slot_id, name, email, status, created_at"


async def json_body(request: Request):
    try:
        return await request.json()
    except Exception:
        raise ApiError(400, "body must be valid JSON")


# ---------- web page ----------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def page():
    return render_page(api_key())


# ---------- level 1: reset and list slots ----------

@app.post("/api/reset")
async def reset(request: Request):
    body = await json_body(request)
    slots = body.get("slots") if isinstance(body, dict) else None
    if not isinstance(slots, list):
        raise ApiError(400, "slots must be an array")
    rows, seen = [], set()
    for s in slots:
        if not isinstance(s, dict):
            raise ApiError(400, "each slot must be an object")
        sid, provider = s.get("id"), s.get("provider")
        if not isinstance(sid, str) or not sid.strip() or not isinstance(provider, str) or not provider.strip():
            raise ApiError(400, "each slot needs id, provider, start and end")
        try:
            start_at, end_at = parse_time(s.get("start")), parse_time(s.get("end"))
        except ValueError:
            raise ApiError(400, f"slot {sid}: start and end must be ISO 8601 date-times")
        if sid in seen:
            raise ApiError(400, f"duplicate slot id {sid}")
        seen.add(sid)
        rows.append((sid, provider, s["start"], s["end"], start_at, end_at))

    with db.transaction() as conn:
        cur = conn.cursor()
        # One reset at a time, and never in the middle of a booking.
        cur.execute("LOCK TABLE slots, bookings, idempotency_keys, booking_attempts IN ACCESS EXCLUSIVE MODE")
        cur.execute("DELETE FROM bookings")
        cur.execute("DELETE FROM idempotency_keys")
        cur.execute("DELETE FROM booking_attempts")
        cur.execute("DELETE FROM slots")
        if rows:
            cur.executemany(
                "INSERT INTO slots (id, provider, start_raw, end_raw, start_at, end_at) VALUES (%s, %s, %s, %s, %s, %s)",
                rows,
            )
    return {"ok": True, "slots": len(rows)}


@app.get("/api/slots")
def list_slots(provider: str | None = None):
    sql = """SELECT s.id, s.provider, s.start_raw, s.end_raw,
                    NOT EXISTS (SELECT 1 FROM bookings b WHERE b.slot_id = s.id AND b.status = 'confirmed')
             FROM slots s"""
    params: tuple = ()
    if provider is not None:
        sql += " WHERE s.provider = %s"
        params = (provider,)
    sql += " ORDER BY s.start_at, s.id"
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"slots": [{"id": r[0], "provider": r[1], "start": r[2], "end": r[3], "available": r[4]} for r in rows]}


# ---------- levels 1-5: book a slot ----------

def _check_rate_limit(cur, email: str) -> None:
    """Level 5: at most RATE_LIMIT attempts per email per window, failed ones included."""
    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("rate:" + email,))
    cur.execute(
        """SELECT count(*), EXTRACT(EPOCH FROM (min(at) + %s * interval '1 second' - clock_timestamp()))
           FROM booking_attempts WHERE email = %s AND at > clock_timestamp() - %s * interval '1 second'""",
        (RATE_WINDOW_SECONDS, email, RATE_WINDOW_SECONDS),
    )
    count, seconds_left = cur.fetchone()
    if count >= RATE_LIMIT:
        retry_after = max(1, math.ceil(float(seconds_left)))
        raise ApiError(429, "too many booking attempts for this email, try again later",
                       {"Retry-After": str(retry_after)})
    cur.execute("INSERT INTO booking_attempts (email) VALUES (%s)", (email,))


def _book(cur, body) -> tuple[int, dict]:
    """Validate and create a booking. Returns (status code, response body)."""
    if not isinstance(body, dict):
        return 400, {"error": "body must be a JSON object"}

    raw_email = body.get("email")
    if isinstance(raw_email, str) and raw_email.strip():
        _check_rate_limit(cur, raw_email.strip().lower())

    fields = {}
    for field in ("slot_id", "name", "email"):
        value = body.get(field)
        if not isinstance(value, str) or not value.strip():
            return 400, {"error": f"{field} is required"}
        fields[field] = value.strip()
    email = fields["email"].lower()
    if not EMAIL_RE.match(email):
        return 400, {"error": "email is not valid"}

    cur.execute("SELECT start_at <= clock_timestamp() FROM slots WHERE id = %s", (fields["slot_id"],))
    slot = cur.fetchone()
    if slot is None:
        return 404, {"error": "slot not found"}
    if slot[0]:
        return 400, {"error": "slot has already started"}

    booking_id = "bk_" + uuid.uuid4().hex[:20]
    cur.execute("SAVEPOINT book")
    try:
        cur.execute(
            f"""INSERT INTO bookings (id, slot_id, name, email, status) VALUES (%s, %s, %s, %s, 'confirmed')
                RETURNING {BOOKING_COLUMNS}""",
            (booking_id, fields["slot_id"], fields["name"], email),
        )
    except Exception as err:
        if db.is_unique_violation(err):
            cur.execute("ROLLBACK TO SAVEPOINT book")
            return 409, {"error": "slot is already booked"}
        raise
    return 201, booking_json(cur.fetchone())


@app.post("/api/bookings")
async def create_booking(request: Request):
    body = await json_body(request)
    key = request.headers.get("idempotency-key")

    with db.transaction() as conn:
        cur = conn.cursor()
        if key:
            # Level 4: requests with the same key run one at a time; replays get the stored response.
            body_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("idem:" + key,))
            cur.execute("SELECT body_hash, status_code, response FROM idempotency_keys WHERE key = %s", (key,))
            stored = cur.fetchone()
            if stored:
                if stored[0] != body_hash:
                    raise ApiError(422, "Idempotency-Key was already used with a different body")
                return JSONResponse(json.loads(stored[2]), status_code=stored[1])

        status, payload = _book(cur, body)  # raises ApiError(429) without storing it

        if key:
            cur.execute(
                "INSERT INTO idempotency_keys (key, body_hash, status_code, response) VALUES (%s, %s, %s, %s)",
                (key, body_hash, status, json.dumps(payload)),
            )
    return JSONResponse(payload, status_code=status)


# ---------- level 4: a person's bookings, paged ----------

def _encode_cursor(created_at: datetime, seq: int) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{seq}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, seq = raw.split("|")
        return datetime.fromisoformat(ts), int(seq)
    except Exception:
        raise ApiError(400, "cursor is not valid")


@app.get("/api/bookings")
def list_bookings(request: Request):
    q = request.query_params
    email = (q.get("email") or "").strip().lower()
    if not email:
        raise ApiError(400, "email is required")
    limit_raw = q.get("limit")
    if limit_raw is None:
        limit = 10
    elif re.fullmatch(r"\d+", limit_raw) and 1 <= int(limit_raw) <= 50:
        limit = int(limit_raw)
    else:
        raise ApiError(400, "limit must be a whole number from 1 to 50")

    sql = f"SELECT {BOOKING_COLUMNS}, seq FROM bookings WHERE email = %s"
    params: list = [email]
    if q.get("cursor"):
        after_ts, after_seq = _decode_cursor(q["cursor"])
        sql += " AND (created_at, seq) > (%s, %s)"
        params += [after_ts, after_seq]
    sql += " ORDER BY created_at, seq LIMIT %s"
    params.append(limit + 1)

    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    page_rows, more = rows[:limit], len(rows) > limit
    last = page_rows[-1] if page_rows else None
    return {
        "bookings": [booking_json(r[:6]) for r in page_rows],
        "next_cursor": _encode_cursor(last[5], last[6]) if more else None,
    }


# ---------- level 1 / 3: get and cancel ----------

@app.get("/api/bookings/{booking_id}")
def get_booking(booking_id: str):
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {BOOKING_COLUMNS} FROM bookings WHERE id = %s", (booking_id,))
        row = cur.fetchone()
    if row is None:
        raise ApiError(404, "booking not found")
    return booking_json(row)


@app.delete("/api/bookings/{booking_id}")
def cancel_booking(booking_id: str):
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE bookings SET status = 'cancelled' WHERE id = %s AND status = 'confirmed' RETURNING {BOOKING_COLUMNS}",
            (booking_id,),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT 1 FROM bookings WHERE id = %s", (booking_id,))
            if cur.fetchone() is None:
                raise ApiError(404, "booking not found")
            raise ApiError(409, "booking is already cancelled")
    return booking_json(row)
