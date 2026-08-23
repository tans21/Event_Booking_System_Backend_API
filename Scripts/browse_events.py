#!/usr/bin/env python3
"""Call GET /api/v1/events (any authenticated user).

Logs in, then lists events with optional filters.

Usage:
    python browse_events.py -e cust@example.com -p secret123
    python browse_events.py -e cust@example.com -p secret123 --q Tech --venue Delhi
    python browse_events.py -e cust@example.com -p secret123 --all   # include sold-out

Override the server with the BASE_URL env var.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse

from api_client import BASE_URL, get_json, load_token, login_or_exit


def main() -> int:
    parser = argparse.ArgumentParser(description="Browse events.")
    # Demo customer creds by default, so the script runs with no arguments.
    parser.add_argument("-e", "--email", default="cust@example.com")
    parser.add_argument("-p", "--password", default="secret123")
    # Optional filters (all default to None and are only sent if provided).
    parser.add_argument("--q", help="Search title/venue")
    parser.add_argument("--venue", help="Filter by venue (partial match)")
    parser.add_argument("--date-from", help="YYYY-MM-DD")
    parser.add_argument("--date-to", help="YYYY-MM-DD")
    # Boolean flag: present -> include sold-out events.
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include sold-out events (available_only=false)",
    )
    # Pagination with sensible defaults if not supplied.
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--size", type=int, default=20)
    args = parser.parse_args()

    # Browsing works for any authenticated user: log in if creds are given,
    # otherwise reuse a cached token (customer preferred, else organizer).
    if args.email and args.password:
        token = login_or_exit(args.email, args.password)
    else:
        token = load_token("customer") or load_token("organizer")
        if not token:
            raise SystemExit(
                "No cached token found. Run `python auth_demo.py` first, "
                "or pass --email/--password."
            )

    # Build the query-string parameters. Only add optional filters when set,
    # so we don't send empty values to the API.
    params = {
        "available_only": "false" if args.all else "true",
        "page": args.page,
        "size": args.size,
    }
    if args.q:
        params["q"] = args.q
    if args.venue:
        params["venue"] = args.venue
    if args.date_from:
        params["date_from"] = args.date_from
    if args.date_to:
        params["date_to"] = args.date_to

    # urlencode turns the dict into "key=value&key=value" (with proper escaping).
    query = urllib.parse.urlencode(params)
    print(f"GET {BASE_URL}/api/v1/events?{query}")
    status, body = get_json(f"/api/v1/events?{query}", token=token)
    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
