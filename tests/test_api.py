"""End-to-end tests against a real Postgres database, in a throwaway schema.

Run:  DATABASE_URL=... python -m pytest     (use the non-pooled URL so SET search_path sticks)
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

if not (os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")):
    pytest.skip("needs TEST_DATABASE_URL or DATABASE_URL", allow_module_level=True)

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or os.environ["DATABASE_URL"]
os.environ["DB_SCHEMA"] = "test_" + uuid.uuid4().hex[:8]
os.environ["API_KEY"] = "test-key"

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402

KEY = {"X-API-Key": "test-key"}
client = TestClient(app, raise_server_exceptions=False)


def ts(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


SLOTS = [
    {"id": "s2", "provider": "Dr Bello", "start": ts(120), "end": ts(150)},
    {"id": "s1", "provider": "Dr Ade", "start": ts(60), "end": ts(90)},
    {"id": "s3", "provider": "Dr Ade", "start": ts(180), "end": ts(210)},
    {"id": "past", "provider": "Dr Ade", "start": ts(-60), "end": ts(-30)},
]


@pytest.fixture(autouse=True)
def fresh():
    r = client.post("/api/reset", json={"slots": SLOTS}, headers=KEY)
    assert r.status_code == 200
    yield


@pytest.fixture(scope="session", autouse=True)
def drop_schema():
    yield
    conn = db._connect()
    conn.cursor().execute(f'DROP SCHEMA IF EXISTS "{os.environ["DB_SCHEMA"]}" CASCADE')
    conn.commit()
    conn.close()


def book(slot="s1", name="Ada Obi", email=None, headers=None):
    body = {"slot_id": slot, "name": name, "email": email or f"{uuid.uuid4().hex[:8]}@example.com"}
    return client.post("/api/bookings", json=body, headers={**KEY, **(headers or {})})


# ---------- level 1 ----------

def test_slots_sorted_with_availability_and_provider_filter():
    slots = client.get("/api/slots", headers=KEY).json()["slots"]
    assert [s["id"] for s in slots] == ["past", "s1", "s2", "s3"]
    assert all(s["available"] for s in slots)
    assert slots[1] == {**SLOTS[1], "available": True}
    ade = client.get("/api/slots", params={"provider": "Dr Ade"}, headers=KEY).json()["slots"]
    assert {s["id"] for s in ade} == {"past", "s1", "s3"}


def test_book_and_look_up():
    r = book(name="  Ada Obi ", email="  Ada@Example.COM ")
    assert r.status_code == 201
    b = r.json()
    assert b["status"] == "confirmed" and b["name"] == "Ada Obi" and b["email"] == "ada@example.com"
    assert set(b) == {"id", "slot_id", "name", "email", "status", "created_at"}
    assert client.get(f"/api/bookings/{b['id']}", headers=KEY).json() == b
    assert client.get("/api/bookings/nope", headers=KEY).status_code == 404
    slots = {s["id"]: s for s in client.get("/api/slots", headers=KEY).json()["slots"]}
    assert slots["s1"]["available"] is False


# ---------- level 2 ----------

def test_api_key_required_everywhere():
    for method, path in [("get", "/api/slots"), ("post", "/api/bookings"), ("get", "/api/bookings/x"),
                         ("delete", "/api/bookings/x"), ("post", "/api/reset"), ("get", "/api/bookings")]:
        assert getattr(client, method)(path).status_code == 401
        r = getattr(client, method)(path, headers={"X-API-Key": "wrong"})
        assert r.status_code == 401 and "error" in r.json()


@pytest.mark.parametrize("body", [
    {"name": "A", "email": "a@b.co"},
    {"slot_id": "s1", "email": "a@b.co"},
    {"slot_id": "s1", "name": "A"},
    {"slot_id": "", "name": "A", "email": "a@b.co"},
    {"slot_id": "s1", "name": "   ", "email": "a@b.co"},
    {"slot_id": "s1", "name": "A", "email": "not-an-email"},
    {"slot_id": "s1", "name": "A", "email": "a@b"},
    {"slot_id": "s1", "name": 5, "email": "a@b.co"},
])
def test_invalid_bookings_rejected(body):
    r = client.post("/api/bookings", json=body, headers=KEY)
    assert r.status_code == 400 and isinstance(r.json()["error"], str)


def test_unknown_and_started_slots():
    assert book(slot="nope").status_code == 404
    assert book(slot="past").status_code == 400


# ---------- level 3 ----------

def test_double_booking_and_cancel():
    first = book().json()
    assert book().status_code == 409
    r = client.delete(f"/api/bookings/{first['id']}", headers=KEY)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.delete(f"/api/bookings/{first['id']}", headers=KEY).status_code == 409
    assert client.delete("/api/bookings/nope", headers=KEY).status_code == 404
    assert book().status_code == 201  # slot is free again


def test_simultaneous_bookings_only_one_wins():
    with ThreadPoolExecutor(max_workers=12) as pool:
        codes = list(pool.map(lambda _: book(slot="s2").status_code, range(12)))
    assert codes.count(201) == 1 and codes.count(409) == 11


# ---------- level 4 ----------

def test_idempotency_key_replays_and_conflicts():
    email = "idem@example.com"
    h = {"Idempotency-Key": "key-1"}
    a = book(email=email, headers=h)
    b = book(email=email, headers=h)
    assert a.status_code == b.status_code == 201 and a.json()["id"] == b.json()["id"]
    assert len(client.get("/api/bookings", params={"email": email}, headers=KEY).json()["bookings"]) == 1
    r = book(slot="s3", email=email, headers=h)
    assert r.status_code == 422


def test_simultaneous_retries_create_one_booking():
    email = "race@example.com"
    with ThreadPoolExecutor(max_workers=5) as pool:
        rs = list(pool.map(lambda _: book(slot="s3", email=email, headers={"Idempotency-Key": "same"}), range(5)))
    assert {r.status_code for r in rs} == {201} and len({r.json()["id"] for r in rs}) == 1


def test_pagination():
    email = "pages@example.com"
    ids =[book(slot=s, email=email).json()["id"] for s in ("s1", "s2", "s3")]
    seen, cursor = [], None
    while True:
        params = {"email": "PAGES@example.com", "limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/bookings", params=params, headers=KEY).json()
        seen += [b["id"] for b in page["bookings"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ids
    for bad in ("0", "51", "abc", "1.5", "-1"):
        assert client.get("/api/bookings", params={"email": email, "limit": bad}, headers=KEY).status_code == 400
    assert client.get("/api/bookings", params={"email": email, "cursor": "!!"}, headers=KEY).status_code == 400


# ---------- level 5 ----------

def test_rate_limit_per_email():
    email = "spam@example.com"
    codes = [book(slot="nope", email=email).status_code for _ in range(5)]
    assert codes == [404] * 5  # failed attempts count too
    r = book(email=email)
    assert r.status_code == 429 and 1 <= int(r.headers["Retry-After"]) <= 60
    assert book(email="someone-else@example.com").status_code == 201
