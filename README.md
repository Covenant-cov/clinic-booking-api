# Clinic booking API

An API that lets patients book appointment slots, plus a web page that uses it: see free slots, book one, see the confirmation, look up and cancel your bookings.

Built with **Python (FastAPI)** and **Postgres (Neon)**, deployed on **Vercel**.

- Web page: `https://clinic-booking-api-puce.vercel.app/`
- API base URL: `https://clinic-booking-api-puce.vercel.app/api`

## Endpoints

Every API request needs the `X-API-Key` header. Every error is `{"error": "<message>"}`.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/reset` | Delete all bookings and replace all slots |
| `GET` | `/api/slots?provider=` | All slots, earliest first, with `available` |
| `POST` | `/api/bookings` | Book a slot (optional `Idempotency-Key` header) |
| `GET` | `/api/bookings/{id}` | One booking |
| `DELETE` | `/api/bookings/{id}` | Cancel a booking and free the slot |
| `GET` | `/api/bookings?email=&limit=&cursor=` | A person's bookings, oldest first, cursor-paged |

## How each level is handled

**Level 1: slots and bookings.** Slots and bookings live in Postgres, so they survive between requests on serverless functions. A slot is available when it has no `confirmed` booking.

**Level 2: API key and validation.** A middleware checks `X-API-Key` against a secret environment variable with a constant-time comparison, returning 401 otherwise. Bookings are validated by hand so every error uses the required format: missing or empty fields, a bad email, or a slot that has already started give 400, and an unknown slot gives 404. Name and email are trimmed, and email is stored in lower case.

**Level 3: no double bookings.** A partial unique index allows at most one `confirmed` booking per slot:

```sql
CREATE UNIQUE INDEX one_confirmed_booking_per_slot ON bookings (slot_id) WHERE status = 'confirmed';
```

The database enforces this, so it holds even when many requests arrive at the same moment on different serverless instances. The losing requests get 409. Cancelling sets the status to `cancelled`, which frees the slot because the index only covers confirmed bookings. Cancelling twice gives 409.

**Level 4: idempotency and paging.** With an `Idempotency-Key`, the request takes a Postgres advisory lock on that key, so simultaneous retries run one at a time. The first stores its status code and response body; later requests with the same key and body get exactly that response back, and a different body gets 422. Rate-limit (429) responses aren't stored, so a client can retry after waiting. The bookings list uses keyset pagination on `(created_at, seq)`, and the cursor is an opaque base64 token, so pages stay stable when new bookings arrive.

**Level 5: rate limiting.** Every booking attempt with an email is recorded, failed ones included. A per-email advisory lock makes the count-then-insert atomic. The 6th attempt within 60 seconds gets 429 with `Retry-After`, the whole seconds until the oldest attempt leaves the window. Other emails are unaffected.

## The web page

`/` is a single page served by the same app. It lists slots by day with a provider filter, books a slot, shows a confirmation, and lets a patient look up, page through and cancel their bookings. Each booking attempt sends an `Idempotency-Key`, so pressing Book again after a network error never books twice.

**Trade-off:** the page calls the API from the browser, so it has to carry the API key. For this task the page and API are one trusted app. In production I'd put patient login in front of a backend-for-frontend, so the browser never holds a shared key.

## Run it yourself

```bash
pip install -r requirements.txt uvicorn
export DATABASE_URL=postgres://...   API_KEY=choose-a-key
uvicorn app.main:app --reload
```

Tests run against a real Postgres database, in a throwaway schema they create and drop:

```bash
pip install pytest httpx
TEST_DATABASE_URL=postgres://... python -m pytest
```

They cover every level, including 12 simultaneous bookings for one slot (exactly one wins) and simultaneous retries with the same idempotency key (one booking).

## Layout

```
app/main.py   Routes, validation, idempotency, rate limiting
app/db.py     Postgres connection and schema
app/page.py   The booking web page
index.py      Vercel entry point (FastAPI app)
tests/        End-to-end tests
```
