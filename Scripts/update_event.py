#!/usr/bin/env python3
"""Call PUT /api/v1/organizer/events/{id} (organizer only).

Updating an event triggers Background Task 2 (Event Update Notification): every
customer with a confirmed booking for that event gets an [EMAIL] log line on the
server console. Only fields you pass are changed.

Usage:
    python update_event.py --event-id 1 --venue "New Grand Arena, Mumbai"
    python update_event.py -e org@example.com -p secret123 --event-id 1 --price 1199.00

Override the server with the BASE_URL env var.
"""
from __future__ import annotations

import argparse
import json
import sys

from api_client import BASE_URL, put_json, token_for


def main() -> int:
    parser = argparse.ArgumentParser(description="Update an event (organizer).")
    # Demo organizer creds by default, so the script runs with no arguments.
    parser.add_argument("-e", "--email", default="org@example.com")
    parser.add_argument("-p", "--password", default="secret123")
    # Which event to update (defaults to the first event).
    parser.add_argument("--event-id", type=int, default=4)
    # Update fields: --venue is prefilled so a no-arg run makes a real change
    # (which is what triggers Task 2). The rest stay None unless you pass them.
    parser.add_argument("--title")
    parser.add_argument("--datetime", help="e.g. 2026-10-15T18:00:00 (IST)")
    parser.add_argument("--venue", default="New Grand Arena, Mumbai")
    parser.add_argument("--tickets", type=int)
    parser.add_argument("--price")
    parser.add_argument("--description")
    args = parser.parse_args()

    # Build the request body from only the flags that were supplied.
    payload: dict = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.datetime is not None:
        payload["event_datetime"] = args.datetime
    if args.venue is not None:
        payload["venue"] = args.venue
    if args.tickets is not None:
        payload["total_tickets"] = args.tickets
    if args.price is not None:
        payload["ticket_price"] = args.price
    if args.description is not None:
        payload["description"] = args.description

    if not payload:
        raise SystemExit(
            "Nothing to update. Pass at least one field, e.g. --venue 'New Hall'."
        )

    token = token_for("organizer", args.email, args.password)
    print(f"PUT {BASE_URL}/api/v1/organizer/events/{args.event_id}")
    status, body = put_json(
        f"/api/v1/organizer/events/{args.event_id}", payload, token=token
    )
    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    if status < 400:
        print(
            "\nWatch your server console for the Task 2 notification lines:\n"
            '  [EMAIL] Event update notification sent to <customer> ...'
        )
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
