# Event Booking System — Backend API

A role-based REST API where **Event Organizers** manage events and **Customers** browse events and book tickets. Built with FastAPI, PostgreSQL, and JWT auth. Two background tasks simulate email notifications (booking confirmation and event-update notification) via console logs.

---

## 1. Project Overview

The system serves two user roles:

| Role | Can do |
|------|--------|
| **Event Organizer** | Register/login, create/update/delete their own events, view their events with booking statistics (tickets sold, revenue, active bookings) |
| **Customer** | Register/login, browse & search events, book tickets, view own bookings, cancel bookings |

API access is controlled by role: organizer-only routes reject customers and vice versa, enforced at the router/dependency layer.

Two asynchronous background tasks run after the HTTP response is sent:
1. **Booking Confirmation** — triggered when a customer books tickets.
2. **Event Update Notification** — triggered when an organizer updates an event; notifies every customer holding a confirmed booking for that event.

Both currently log a single line to the console (as specified) instead of sending real email.

---

## 2. Tech Stack & Why

| Choice | Reason |
|--------|--------|
| **FastAPI** | Native async, automatic OpenAPI/Swagger docs, Pydantic request/response validation out of the box. |
| **PostgreSQL + asyncpg** | Production-grade relational DB; `asyncpg` is a fast async driver so DB calls never block the event loop. |
| **SQLAlchemy 2.0 (async)** | Mature ORM with typed `Mapped[...]` models and async sessions. |
| **Alembic** | Versioned, reviewable schema migrations kept under source control. |
| **JWT (`python-jose`) + `bcrypt`** | Stateless auth. The role is embedded in the token, so authorization needs no session store. Passwords are hashed with bcrypt. |
| **FastAPI `BackgroundTasks`** | In-process async tasks that run after the response. No Redis/Celery broker needed for this scope. |

> **Password hashing note:** we call `bcrypt` directly rather than through `passlib`, because `passlib` 1.7.4 is incompatible with `bcrypt` 5.x on recent Python versions. bcrypt only considers the first 72 bytes of a password, which we handle explicitly in [app/services/auth_service.py](app/services/auth_service.py).

---

## 3. Authentication & Authorization

### JWT structure
On login, the server issues a JWT whose payload is:

```json
{
  "sub": "1",              // user id (string, standard JWT subject)
  "email": "user@example.com",
  "role": "organizer",     // or "customer" — the authorization claim
  "iat": 1755936000,
  "exp": 1755939600
}
```

**Why the role lives in the token:** authorization decisions (`is this user an organizer?`) require no database lookup — the token is self-contained. Identity is still re-validated against the DB on each request (to honor deactivated accounts).

### Dependency chain — [app/dependencies/auth.py](app/dependencies/auth.py)

```
HTTPBearer  →  get_current_user  →  require_organizer / require_customer
```

- `get_current_user` decodes the bearer token, loads the `User`, and rejects unknown/inactive users with `401`.
- `require_organizer` / `require_customer` wrap it and raise `403` if the role doesn't match.

The organizer router applies the guard **once at the router level** (`dependencies=[Depends(require_organizer)]`), so every organizer route is protected by a single declaration — there's no way to forget to protect a new route.

**Why we use `HTTPBearer` (not `OAuth2PasswordBearer`):** login accepts a JSON body (`email` + `password`), not an OAuth2 form. `HTTPBearer` gives Swagger a simple "paste your token" Authorize dialog that pairs cleanly with the JSON login endpoint.

**Why event-browsing isn't role-restricted:** `GET /events` and `GET /events/{id}` only require a valid login, not the customer role, so an organizer can also browse the catalog. Only booking actions require the customer role.

### Ownership checks
Role guards answer "what kind of user is this?"; **ownership** ("does this user own this row?") is enforced inside the service layer — e.g. `event.organizer_id != current_user.id → 403` in [app/services/event_service.py](app/services/event_service.py), and the equivalent for bookings in [app/services/booking_service.py](app/services/booking_service.py).

---

## 4. Database Schema

Three tables — see [app/models/](app/models/) and the migration in [alembic/versions/0001_initial_schema.py](alembic/versions/0001_initial_schema.py).

### `users`
`id, email (unique), hashed_password, full_name, role (enum), is_active, created_at`

### `events`
`id, organizer_id (FK→users), title, description, event_datetime, venue, total_tickets, tickets_available, ticket_price, is_active, created_at, updated_at`

### `bookings`
`id, customer_id (FK→users), event_id (FK→events), quantity, total_price, status (enum: confirmed|cancelled), booked_at, cancelled_at`

### Design decisions

- **`tickets_available` is a stored column, not a computed aggregate.** Computing availability as `total_tickets − SUM(bookings.quantity)` would require a subquery on every read and makes the "only show events with tickets left" filter (`WHERE tickets_available > 0`) awkward. Instead we store the number and decrement/increment it atomically inside the same transaction as the booking. This is the standard ticketing-inventory pattern.

- **Events are soft-deleted (`is_active = False`), not hard-deleted.** A hard delete would orphan or cascade-destroy booking history. Soft delete preserves the audit trail, keeps customers' past bookings visible, and is reversible.

- **`bookings.status` is an enum with a `cancelled_at` timestamp** rather than deleting cancelled rows — this keeps a full history of cancellations for auditing and lets `GET /bookings?status=cancelled` work.

- **Concurrency safety:** `create_booking` and `cancel_booking` issue `SELECT ... FOR UPDATE` on the event row before adjusting `tickets_available`, so two simultaneous bookings for the last tickets can't both succeed.

---

## 5. Background Tasks

Both live in [app/tasks/notifications.py](app/tasks/notifications.py) and are scheduled with FastAPI's `BackgroundTasks.add_task(...)`.

### Task 1 — Booking Confirmation
- **Trigger:** `POST /api/v1/bookings`, after the booking is committed ([app/routers/customer.py](app/routers/customer.py)).
- **Output (one line):**
  ```
  [EMAIL] Confirmation sent to cust@example.com for "Tech Summit 2026" — 2 ticket(s), $1998.00 (Booking #1)
  ```

### Task 2 — Event Update Notification
- **Trigger:** `PUT /api/v1/organizer/events/{id}`, after the update is committed ([app/routers/organizer.py](app/routers/organizer.py)). Only fires if at least one field actually changed.
- **Behavior:** queries every customer with a `confirmed` booking for that event and logs one line each:
  ```
  [EMAIL] Event update notification sent to cust@example.com — "Tech Summit 2026" updated: venue
  ```

### Design decisions

- **Why FastAPI `BackgroundTasks` and not Celery/Redis:** the tasks are short, in-process, and don't need retries or a separate worker fleet for this scope. No extra infrastructure to run.

- **Why Task 2 receives a session *factory*, not the request's DB session:** FastAPI closes the request-scoped `AsyncSession` as soon as the response is sent — before the background task runs. Reusing it would raise an error. The task instead receives `AsyncSessionLocal` and opens its own short-lived session (`async with session_factory() as db:`).

- **`changed_fields` drives the notification content:** the update service returns the list of fields that actually changed, and only those are mentioned in the notification (and the task is skipped entirely if nothing changed).

---

## 6. API Reference

Base path: `/api/v1`. Interactive docs at `/docs` once running.

### Auth (public)
| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/auth/register` | `email, password, full_name, role` | `role` ∈ `organizer` \| `customer` |
| POST | `/auth/login` | `email, password` | returns `access_token`, `role`, `user_id` |

### Organizer (Bearer token, role = organizer)
| Method | Path | Notes |
|---|---|---|
| POST | `/organizer/events` | create event |
| GET | `/organizer/events` | own events + stats (paginated) |
| GET | `/organizer/events/{id}` | one event + stats |
| PUT | `/organizer/events/{id}` | update → **Task 2** |
| DELETE | `/organizer/events/{id}` | soft-delete |

### Browsing (Bearer token, any role)
| Method | Path | Query params |
|---|---|---|
| GET | `/events` | `q, date_from, date_to, venue, available_only, page, size` |
| GET | `/events/{id}` | — |

### Bookings (Bearer token, role = customer)
| Method | Path | Notes |
|---|---|---|
| POST | `/bookings` | `event_id, quantity` → **Task 1** |
| GET | `/bookings` | own bookings; `?status=confirmed\|cancelled` |
| GET | `/bookings/{id}` | one booking (with event) |
| DELETE | `/bookings/{id}` | cancel → restores `tickets_available` |

### Other API choices
- **Versioned prefix `/api/v1`** so future breaking changes can live under `/api/v2`.
- **Pagination** (`page`, `size`) on every list endpoint.
- Consistent error bodies via FastAPI's `{"detail": "..."}`.

### Date & time handling
The API presents all datetimes in **IST (UTC+05:30)**, formatted to whole seconds with
no timezone suffix — e.g. `2026-10-15T09:00:00`. Under the hood it follows the standard
**store-UTC / display-IST** model, all in one place ([app/schemas/types.py](app/schemas/types.py)):

- **Storage:** datetime columns are `timestamp with time zone` and hold **UTC** instants —
  the unambiguous, standard way to persist time regardless of server location.
- **Input:** a naive `event_datetime` (no offset) is interpreted as IST wall-clock and
  converted to UTC for storage — see `normalize_datetime`.
- **Output:** the shared `SecondsDateTime` type converts every response datetime
  (`event_datetime`, `created_at`, `updated_at`, `booked_at`, `cancelled_at`) back to IST
  seconds. So `2026-10-15T09:00:00` in round-trips to `2026-10-15T09:00:00` out, while the
  DB holds `2026-10-15 03:30:00+00`.

---

## 7. Setup & Running

### Prerequisites
- Python 3.11+
- PostgreSQL running locally

### Steps
```bash
# 1. Create and activate a virtualenv
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database
createdb event_booking

# 4. Configure environment
cp .env.example .env
#   Edit .env: set a strong SECRET_KEY (openssl rand -hex 32)
#   and point DATABASE_URL at your Postgres instance, e.g.:
#   postgresql+asyncpg://<user>:<password>@localhost:5432/event_booking

# 5. Run migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for Swagger UI. Click **Authorize**, paste the `access_token` from `/auth/login`, and call the protected endpoints.

> **macOS + Homebrew Postgres note:** if `pg_ctl start` fails with *"postmaster became multithreaded during startup"*, start it with `LC_ALL=C` set.

---

## 8. Testing the System

Manual end-to-end flow (via Swagger or curl):

1. Register an **organizer** → `POST /auth/register` with `role: organizer`.
2. Register a **customer** → `POST /auth/register` with `role: customer`.
3. Log both in → `POST /auth/login`, copy each `access_token`.
4. As organizer, create an event → `POST /organizer/events`.
5. As customer, browse → `GET /events` (confirm the event appears).
6. As customer, book tickets → `POST /bookings`. **Watch the server console for the `[EMAIL] Confirmation sent...` line (Task 1).**
7. As customer, view bookings → `GET /bookings`, and check inventory dropped via `GET /events/{id}`.
8. As organizer, update the event → `PUT /organizer/events/{id}`. **Watch the console for `[EMAIL] Event update notification...` (Task 2).**
9. As customer, cancel → `DELETE /bookings/{id}`, and confirm `tickets_available` is restored.

**RBAC checks:**
- Customer token on `POST /organizer/events` → `403`.
- Organizer token on `POST /bookings` → `403`.
- No Authorization header on a protected route → `401`.

**Edge cases handled:**
- Booking more tickets than available → `400 Not enough tickets available`.
- Cancelling an already-cancelled booking → `400`.
- Reducing `total_tickets` below the number already sold → `400`.

### Automated tests

A `pytest` suite in [tests/](tests/) covers positive, negative, and edge cases across
auth, events, bookings, and both background tasks (53 tests). It runs against a
dedicated database so it never touches dev data.

```bash
# one-time: install dev deps and create the test database
pip install -r requirements-dev.txt
createdb event_booking_test        # or set TEST_DATABASE_URL to any Postgres DB

# run the suite
pytest                             # or: pytest -v
```

The test database URL defaults to `<DATABASE_URL>_test` and can be overridden with the
`TEST_DATABASE_URL` env var. Fixtures create the schema once and truncate tables before
each test for isolation (see [tests/conftest.py](tests/conftest.py)).

Coverage highlights:
- **Auth** — register/login success, duplicate email, invalid role/email, short password,
  wrong password, missing/garbage token.
- **Events** — CRUD, organizer-only RBAC, ownership checks, booking stats, browse
  search/venue/availability filters, soft delete, ticket-count adjustment rules.
- **Bookings** — book/list/cancel, inventory decrement & restore, overbooking,
  exact-availability, inactive-event, non-owner access, invalid quantity.
- **Notifications** — both tasks log correctly; event-update notifies only customers with
  confirmed bookings.

---

## 9. Project Structure

```
app/
├── main.py              # app assembly, router registration, lifespan
├── config.py            # settings from .env
├── database.py          # async engine, session factory, Base
├── models/              # SQLAlchemy models: user, event, booking
├── schemas/             # Pydantic request/response models
├── dependencies/        # get_db, auth guards
├── services/            # business logic: auth, events, bookings
├── tasks/               # background notification tasks
└── routers/             # auth, organizer, customer endpoints
alembic/                 # migrations
```
