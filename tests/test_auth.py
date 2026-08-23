"""Auth API tests: register + login, positive / negative / edge cases."""
from __future__ import annotations

from tests.conftest import register

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"


# --- register: positive -----------------------------------------------------


async def test_register_organizer_success(client):
    resp = await register(client, "org@x.com", "secret123", "Olivia", "organizer")
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "org@x.com"
    assert body["role"] == "organizer"
    assert body["is_active"] is True
    assert "id" in body
    assert "hashed_password" not in body  # never leak the password hash


async def test_register_customer_success(client):
    resp = await register(client, "cust@x.com", "secret123", "Cara", "customer")
    assert resp.status_code == 201
    assert resp.json()["role"] == "customer"


# --- register: negative / edge ----------------------------------------------


async def test_register_duplicate_email(client):
    await register(client, "dup@x.com", "secret123", "First", "customer")
    resp = await register(client, "dup@x.com", "secret123", "Second", "organizer")
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"].lower()


async def test_register_invalid_role(client):
    resp = await register(client, "bad@x.com", "secret123", "Bad", "admin")
    assert resp.status_code == 422


async def test_register_short_password(client):
    resp = await register(client, "short@x.com", "123", "Short", "customer")
    assert resp.status_code == 422


async def test_register_invalid_email(client):
    resp = await register(client, "not-an-email", "secret123", "Bad", "customer")
    assert resp.status_code == 422


async def test_register_missing_fields(client):
    resp = await client.post(REGISTER, json={"email": "x@x.com"})
    assert resp.status_code == 422


# --- login: positive --------------------------------------------------------


async def test_login_success(client):
    await register(client, "login@x.com", "secret123", "Log In", "organizer")
    resp = await client.post(
        LOGIN, json={"email": "login@x.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "organizer"
    assert body["user_id"] >= 1
    assert body["access_token"]


# --- login: negative --------------------------------------------------------


async def test_login_wrong_password(client):
    await register(client, "wp@x.com", "secret123", "WP", "customer")
    resp = await client.post(LOGIN, json={"email": "wp@x.com", "password": "nope"})
    assert resp.status_code == 401


async def test_login_nonexistent_user(client):
    resp = await client.post(
        LOGIN, json={"email": "ghost@x.com", "password": "secret123"}
    )
    assert resp.status_code == 401


# --- token enforcement ------------------------------------------------------


async def test_protected_route_without_token(client):
    resp = await client.post("/api/v1/organizer/events", json={})
    assert resp.status_code == 401


async def test_protected_route_with_garbage_token(client):
    resp = await client.get(
        "/api/v1/bookings", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert resp.status_code == 401
