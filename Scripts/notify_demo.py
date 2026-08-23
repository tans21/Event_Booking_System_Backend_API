#!/usr/bin/env python3
"""End-to-end demo that triggers BOTH email background tasks.

Run this, then watch your running server's console for two kinds of [EMAIL] lines:
  1. Booking Confirmation      — fired when the customer books tickets.
  2. Event Update Notification — fired when the organizer updates the event
                                 (sent to every customer with a confirmed booking).

All values are hard-coded below — just edit them and run:
    python notify_demo.py

Requires the API running (default http://127.0.0.1:8000; override with BASE_URL).
"""
from __future__ import annotations

import sys

from api_client import (
    BASE_URL,
    get_json,
    login_or_exit,
    post_json,
    put_json,
    register,
)

# ---- Edit these values to taste --------------------------------------------
ORGANIZER = {
    "email": "org@example.com",
    "password": "secret123",
    "full_name": "Olivia Organizer",
}
CUSTOMER = {
    "email": "cust@example.com",
    "password": "secret123",
    "full_name": "Cara Customer",
}
EVENT = {
    "title": "Tech Summit 2026",
    "description": "Annual conference",
    "event_datetime": "2026-10-15T09:00:00",  # IST
    "venue": "Convention Center, Delhi",
    "total_tickets": 100,
    "ticket_price": "999.00",
}
BOOK_QUANTITY = 2
UPDATED_VENUE = "New Grand Arena, Mumbai"  # the change that triggers Task 2
# ----------------------------------------------------------------------------


def ensure_registered(user: dict, role: str) -> None:
    """Register a user, ignoring the 'already registered' case on repeat runs."""
    status, body = register(user["email"], user["password"], user["full_name"], role)
    if status == 201:
        print(f"  registered {role}: {user['email']}")
    elif status == 400 and "already registered" in str(body).lower():
        print(f"  {role} already exists: {user['email']}")
    else:
        raise SystemExit(f"  failed to register {role}: HTTP {status} {body}")


def main() -> int:
    print(f"Target server: {BASE_URL}\n")

    print("1) Ensure demo accounts exist")
    ensure_registered(ORGANIZER, "organizer")
    ensure_registered(CUSTOMER, "customer")

    print("\n2) Log in")
    org_token = login_or_exit(ORGANIZER["email"], ORGANIZER["password"])
    cust_token = login_or_exit(CUSTOMER["email"], CUSTOMER["password"])
    print("  got organizer + customer tokens")

    print("\n3) Organizer creates an event")
    status, event = post_json("/api/v1/organizer/events", EVENT, token=org_token)
    if status != 201:
        raise SystemExit(f"  create event failed: HTTP {status} {event}")
    event_id = event["id"]
    print(f"  created event id={event_id} '{event['title']}'")

    print("\n4) Customer books tickets  ->  triggers TASK 1 (booking confirmation)")
    status, booking = post_json(
        "/api/v1/bookings",
        {"event_id": event_id, "quantity": BOOK_QUANTITY},
        token=cust_token,
    )
    if status != 201:
        raise SystemExit(f"  booking failed: HTTP {status} {booking}")
    print(f"  booked {BOOK_QUANTITY} ticket(s), booking id={booking['id']}")

    print("\n5) Organizer updates the event  ->  triggers TASK 2 (update notification)")
    status, updated = put_json(
        f"/api/v1/organizer/events/{event_id}",
        {"venue": UPDATED_VENUE},
        token=org_token,
    )
    if status != 200:
        raise SystemExit(f"  update failed: HTTP {status} {updated}")
    print(f"  venue changed to '{updated['venue']}'")

    print("\nDone. Look at your SERVER console for two [EMAIL] lines, e.g.:")
    print(
        f'  [EMAIL] Confirmation sent to {CUSTOMER["email"]} for '
        f'"{EVENT["title"]}" ...'
    )
    print(
        f'  [EMAIL] Event update notification sent to {CUSTOMER["email"]} — '
        f'"{EVENT["title"]}" updated: venue'
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
