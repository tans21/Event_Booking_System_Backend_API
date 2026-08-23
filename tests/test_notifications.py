"""Tests for the two background tasks (simulated email notifications)."""
from __future__ import annotations

import logging
from decimal import Decimal

from app.tasks.notifications import (
    send_booking_confirmation,
    send_event_update_notifications,
)
from tests.conftest import TestSessionLocal, create_event

LOGGER = "event_booking.notifications"


# --- Task 1: booking confirmation -------------------------------------------


async def test_booking_confirmation_logs_summary(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        await send_booking_confirmation(
            booking_id=15,
            customer_email="alice@example.com",
            event_title="Tech Summit 2026",
            quantity=2,
            total_price=Decimal("1998.00"),
        )
    messages = [r.getMessage() for r in caplog.records]
    assert any("[EMAIL] Confirmation sent to alice@example.com" in m for m in messages)
    assert any("Tech Summit 2026" in m and "1998.00" in m for m in messages)


# --- Task 2: event update notification --------------------------------------


async def test_event_update_notifies_booked_customers(
    client, organizer_headers, customer_headers, caplog
):
    event = await create_event(client, organizer_headers)
    await client.post(
        "/api/v1/bookings",
        json={"event_id": event["id"], "quantity": 1},
        headers=customer_headers,
    )

    with caplog.at_level(logging.INFO, logger=LOGGER):
        await send_event_update_notifications(
            event_id=event["id"],
            event_title=event["title"],
            changed_fields=["venue", "event_datetime"],
            session_factory=TestSessionLocal,
        )

    messages = [r.getMessage() for r in caplog.records]
    # the customer who booked is notified, with the list of changed fields
    assert any(
        "cust@example.com" in m and "venue, event_datetime" in m for m in messages
    )


async def test_event_update_only_notifies_confirmed_bookings(
    client, organizer_headers, customer_headers, caplog
):
    event = await create_event(client, organizer_headers)
    r = await client.post(
        "/api/v1/bookings",
        json={"event_id": event["id"], "quantity": 1},
        headers=customer_headers,
    )
    # cancel it -> should NOT be notified
    await client.delete(
        f"/api/v1/bookings/{r.json()['id']}", headers=customer_headers
    )

    with caplog.at_level(logging.INFO, logger=LOGGER):
        await send_event_update_notifications(
            event_id=event["id"],
            event_title=event["title"],
            changed_fields=["venue"],
            session_factory=TestSessionLocal,
        )

    messages = [r.getMessage() for r in caplog.records]
    assert not any("notification sent to cust@example.com" in m for m in messages)
    # and it reports that there was no one to notify
    assert any("no customers with active bookings" in m.lower() for m in messages)


async def test_event_update_no_bookings_at_all(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        await send_event_update_notifications(
            event_id=424242,
            event_title="Ghost Event",
            changed_fields=["venue"],
            session_factory=TestSessionLocal,
        )
    messages = [r.getMessage() for r in caplog.records]
    assert any("no customers with active bookings" in m.lower() for m in messages)
