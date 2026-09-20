"""Shared pytest fixtures.

Tests run against a dedicated PostgreSQL database (``event_booking_test`` by
default, overridable via TEST_DATABASE_URL) so they never touch dev data. Tables
are (re)created and truncated before each test for full isolation.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  ensure all models register on Base.metadata
import app.routers.organizer as organizer_router
import app.tasks.notifications as notifications
from app.config import settings
from app.database import Base
from app.dependencies.db import get_db
from app.main import app


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    # Derive "<dev-db>_test" from the configured DATABASE_URL.
    base, _, name = settings.DATABASE_URL.rpartition("/")
    return f"{base}/{name}_test"


TEST_DATABASE_URL = _test_database_url()

# NullPool: don't cache connections across tests. pytest-asyncio uses a fresh
# event loop per test, and a pooled connection bound to a previous loop raises
# InterfaceError when reused.
test_engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


_tables_created = False


@pytest_asyncio.fixture(autouse=True)
async def _db_setup():
    """Create tables once, then truncate them before each test for isolation."""
    global _tables_created
    async with test_engine.begin() as conn:
        if not _tables_created:
            await conn.run_sync(Base.metadata.create_all)
            _tables_created = True
        await conn.execute(
            text("TRUNCATE bookings, events, users RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture(autouse=True)
def mock_email(monkeypatch):
    """Intercept SMTP sends so tests never hit the network or send real mail.

    Also disables EMAIL_TO_OVERRIDE so tests can assert the *correct* customer
    is targeted (the override is only an optional demo redirect).
    """
    sent: list[dict] = []

    async def _fake_send_email(*, to, subject, html):
        sent.append({"to": to, "subject": subject, "html": html})

    monkeypatch.setattr(notifications, "_send_email", _fake_send_email)
    monkeypatch.setattr(settings, "EMAIL_TO_OVERRIDE", "")
    return sent


async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(monkeypatch):
    # Route the request DB session and the event-update background task to the
    # test database instead of the dev one.
    monkeypatch.setattr(organizer_router, "AsyncSessionLocal", TestSessionLocal)
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- auth helpers -----------------------------------------------------------


async def register(client: AsyncClient, email, password, full_name, role):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": role,
        },
    )


async def auth_header(client: AsyncClient, email, password, full_name, role) -> dict:
    """Register (best effort) + log in, returning an Authorization header dict."""
    await register(client, email, password, full_name, role)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def organizer_headers(client) -> dict:
    return await auth_header(
        client, "org@example.com", "secret123", "Olivia Organizer", "organizer"
    )


@pytest_asyncio.fixture
async def customer_headers(client) -> dict:
    return await auth_header(
        client, "cust@example.com", "secret123", "Cara Customer", "customer"
    )


# --- factories --------------------------------------------------------------

VALID_EVENT = {
    "title": "Tech Summit 2026",
    "description": "Annual conference",
    "event_datetime": "2026-10-15T09:00:00",
    "venue": "Convention Center, Delhi",
    "total_tickets": 100,
    "ticket_price": "999.00",
}


async def create_event(client, headers, **overrides) -> dict:
    payload = {**VALID_EVENT, **overrides}
    resp = await client.post("/api/v1/organizer/events", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()
