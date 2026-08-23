"""Booking API tests: book / list / cancel, overbooking, RBAC, edge cases."""
from __future__ import annotations

from tests.conftest import auth_header, create_event

BOOKINGS = "/api/v1/bookings"
EVENTS = "/api/v1/organizer/events"
BROWSE = "/api/v1/events"


async def _make_event(client, organizer_headers, **overrides) -> int:
    event = await create_event(client, organizer_headers, **overrides)
    return event["id"]


# --- book: positive ---------------------------------------------------------


async def test_book_success_decrements_inventory(
    client, organizer_headers, customer_headers
):
    event_id = await _make_event(client, organizer_headers, total_tickets=100)
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 2}, headers=customer_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["quantity"] == 2
    assert body["status"] == "confirmed"
    assert body["total_price"] == "1998.00"  # 2 * 999.00

    detail = await client.get(f"{BROWSE}/{event_id}", headers=customer_headers)
    assert detail.json()["tickets_available"] == 98


async def test_book_exact_availability(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers, total_tickets=5)
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 5}, headers=customer_headers
    )
    assert resp.status_code == 201
    detail = await client.get(f"{BROWSE}/{event_id}", headers=customer_headers)
    assert detail.json()["tickets_available"] == 0


# --- book: negative / RBAC / edge -------------------------------------------


async def test_book_as_organizer_forbidden(client, organizer_headers):
    event_id = await _make_event(client, organizer_headers)
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=organizer_headers
    )
    assert resp.status_code == 403


async def test_book_unauthenticated(client):
    resp = await client.post(BOOKINGS, json={"event_id": 1, "quantity": 1})
    assert resp.status_code == 401


async def test_book_nonexistent_event(client, customer_headers):
    resp = await client.post(
        BOOKINGS, json={"event_id": 9999, "quantity": 1}, headers=customer_headers
    )
    assert resp.status_code == 404


async def test_book_inactive_event(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers)
    await client.delete(f"{EVENTS}/{event_id}", headers=organizer_headers)  # soft delete
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=customer_headers
    )
    assert resp.status_code == 404


async def test_book_exceeds_availability(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers, total_tickets=3)
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 4}, headers=customer_headers
    )
    assert resp.status_code == 400
    assert "not enough" in resp.json()["detail"].lower()


async def test_book_zero_quantity(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers)
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 0}, headers=customer_headers
    )
    assert resp.status_code == 422


async def test_book_negative_quantity(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers)
    resp = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": -2}, headers=customer_headers
    )
    assert resp.status_code == 422


# --- list -------------------------------------------------------------------


async def test_list_my_bookings(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers)
    await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=customer_headers
    )
    resp = await client.get(BOOKINGS, headers=customer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    # nested event summary present
    assert data["items"][0]["event"]["id"] == event_id


async def test_list_bookings_status_filter(
    client, organizer_headers, customer_headers
):
    event_id = await _make_event(client, organizer_headers)
    r = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=customer_headers
    )
    booking_id = r.json()["id"]
    await client.delete(f"{BOOKINGS}/{booking_id}", headers=customer_headers)

    confirmed = await client.get(
        BOOKINGS, params={"status": "confirmed"}, headers=customer_headers
    )
    assert confirmed.json()["total"] == 0
    cancelled = await client.get(
        BOOKINGS, params={"status": "cancelled"}, headers=customer_headers
    )
    assert cancelled.json()["total"] == 1


async def test_get_booking_of_other_customer_forbidden(
    client, organizer_headers, customer_headers
):
    event_id = await _make_event(client, organizer_headers)
    r = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=customer_headers
    )
    booking_id = r.json()["id"]
    other = await auth_header(client, "cust2@x.com", "secret123", "Cust2", "customer")
    resp = await client.get(f"{BOOKINGS}/{booking_id}", headers=other)
    assert resp.status_code == 403


async def test_get_booking_not_found(client, customer_headers):
    resp = await client.get(f"{BOOKINGS}/9999", headers=customer_headers)
    assert resp.status_code == 404


# --- cancel -----------------------------------------------------------------


async def test_cancel_restores_inventory(
    client, organizer_headers, customer_headers
):
    event_id = await _make_event(client, organizer_headers, total_tickets=10)
    r = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 4}, headers=customer_headers
    )
    booking_id = r.json()["id"]

    before = await client.get(f"{BROWSE}/{event_id}", headers=customer_headers)
    assert before.json()["tickets_available"] == 6

    resp = await client.delete(f"{BOOKINGS}/{booking_id}", headers=customer_headers)
    assert resp.status_code == 200

    after = await client.get(f"{BROWSE}/{event_id}", headers=customer_headers)
    assert after.json()["tickets_available"] == 10


async def test_cancel_already_cancelled(client, organizer_headers, customer_headers):
    event_id = await _make_event(client, organizer_headers)
    r = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=customer_headers
    )
    booking_id = r.json()["id"]
    await client.delete(f"{BOOKINGS}/{booking_id}", headers=customer_headers)
    resp = await client.delete(f"{BOOKINGS}/{booking_id}", headers=customer_headers)
    assert resp.status_code == 400


async def test_cancel_of_other_customer_forbidden(
    client, organizer_headers, customer_headers
):
    event_id = await _make_event(client, organizer_headers)
    r = await client.post(
        BOOKINGS, json={"event_id": event_id, "quantity": 1}, headers=customer_headers
    )
    booking_id = r.json()["id"]
    other = await auth_header(client, "cust3@x.com", "secret123", "Cust3", "customer")
    resp = await client.delete(f"{BOOKINGS}/{booking_id}", headers=other)
    assert resp.status_code == 403


async def test_cancel_not_found(client, customer_headers):
    resp = await client.delete(f"{BOOKINGS}/9999", headers=customer_headers)
    assert resp.status_code == 404
