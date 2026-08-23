#!/usr/bin/env python3
"""Book tickets and manage bookings (customer only).

Logs in as a customer, then performs one of:
  - book   : POST   /api/v1/bookings
  - list   : GET    /api/v1/bookings
  - cancel : DELETE /api/v1/bookings/{id}

Usage (all args have demo defaults, so it runs with none):
    python book_ticket.py                                 # book event 1, qty 2
    python book_ticket.py --action list
    python book_ticket.py --action cancel --booking-id 1
    python book_ticket.py --action book --event-id 2 --quantity 3

Override the server with the BASE_URL env var.
"""
from __future__ import annotations

import argparse
import json
import sys

from api_client import BASE_URL, delete, get_json, post_json, token_for


def main() -> int:
    parser = argparse.ArgumentParser(description="Book / list / cancel tickets.")
    # Demo customer creds by default, so the script runs with no arguments.
    parser.add_argument("-e", "--email", default="cust@example.com")
    parser.add_argument("-p", "--password", default="secret123")
    # Which operation to run. choices restricts it; default "book" runs with no args.
    parser.add_argument(
        "--action", choices=["book", "list", "cancel"], default="book"
    )
    # Demo defaults for the operation-specific arguments.
    parser.add_argument("--event-id", type=int, default=4)
    parser.add_argument("--quantity", type=int, default=2)
    parser.add_argument("--booking-id", type=int, default=1)

    args = parser.parse_args()
    # Resolve the customer token (logs in with the creds above).
    token = token_for("customer", args.email, args.password)

    # Dispatch on the chosen sub-command; each hits a different endpoint/verb.
    if args.action == "book":
        payload = {"event_id": args.event_id, "quantity": args.quantity}
        print(f"POST {BASE_URL}/api/v1/bookings")
        status, body = post_json("/api/v1/bookings", payload, token=token)
    elif args.action == "list":
        print(f"GET {BASE_URL}/api/v1/bookings")
        status, body = get_json("/api/v1/bookings", token=token)
    else:  # cancel
        print(f"DELETE {BASE_URL}/api/v1/bookings/{args.booking_id}")
        status, body = delete(f"/api/v1/bookings/{args.booking_id}", token=token)

    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
