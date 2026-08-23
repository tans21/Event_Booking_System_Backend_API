#!/usr/bin/env python3
"""Call POST /api/v1/organizer/events (organizer only).

Logs in with the given organizer credentials, then creates an event.

Usage:
    python create_event.py -e org@example.com -p secret123 \
        --title "Tech Summit 2026" --datetime 2026-10-15T09:00:00 \
        --venue "Convention Center, Delhi" --tickets 100 --price 999.00 \
        --description "Annual conference"

Override the server with the BASE_URL env var.
"""
from __future__ import annotations

import argparse
import json
import sys

from api_client import BASE_URL, post_json, token_for


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an event (organizer).")
    # Demo organizer creds by default, so the script logs in and runs with no args.
    parser.add_argument("-e", "--email", default="org@example.com")
    parser.add_argument("-p", "--password", default="secret123")
    # Event fields — all prefilled with demo values; override any with its flag.
    parser.add_argument("--title", default="Tech Summit 2026")
    parser.add_argument(
        "--datetime",
        default="2026-10-15T09:00:00",
        help="Event start, e.g. 2026-10-15T09:00:00 (IST)",
    )
    parser.add_argument("--venue", default="Convention Center, Delhi")
    # type=int converts the string argument to an int (and errors on non-numbers).
    parser.add_argument("--tickets", type=int, default=100)
    parser.add_argument("--price", default="999.00")
    parser.add_argument("--description", default="Annual conference")
    args = parser.parse_args()

    # Resolve the organizer token: log in if creds were passed, else use the cache.
    token = token_for("organizer", args.email, args.password)
    # Build the JSON request body the API expects.
    payload = {
        "title": args.title,
        "description": args.description,
        "event_datetime": args.datetime,
        "venue": args.venue,
        "total_tickets": args.tickets,
        "ticket_price": args.price,
    }

    print(f"POST {BASE_URL}/api/v1/organizer/events")
    status, body = post_json("/api/v1/organizer/events", payload, token=token)
    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
