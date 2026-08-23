#!/usr/bin/env python3
"""Demo: register + login for both an organizer and a customer.

Registers two users (ignoring "already registered" on re-runs), logs both in,
and prints their JWT tokens. Requires the API running.

Usage:
    python auth_demo.py
    BASE_URL=http://localhost:9000 python auth_demo.py
"""
from __future__ import annotations

import sys

from api_client import BASE_URL, TOKEN_FILE, login, register, save_token

# The two demo accounts: (email, password, full_name, role).
USERS = [
    ("org@example.com", "secret123", "Olivia Organizer", "organizer"),
    ("cust@example.com", "secret123", "Cara Customer", "customer"),
]


def main() -> int:
    print(f"Target server: {BASE_URL}\n")

    print("== Register ==")
    # Register each demo user. Tuple-unpacking pulls the 4 fields out of each row.
    for email, password, name, role in USERS:
        status, body = register(email, password, name, role)
        if status == 201:
            print(f"  [created] {role:9} {email} (id={body.get('id')})")
        # A repeat run hits "already registered" (400) — treat that as fine.
        elif status == 400 and "already registered" in str(body).lower():
            print(f"  [exists ] {role:9} {email}")
        else:
            print(f"  [error {status}] {email}: {body}")

    print("\n== Login ==")
    tokens: dict[str, str] = {}  # role -> token, used for the summary at the end
    # _name is unused here; the leading underscore signals "intentionally ignored".
    for email, password, _name, role in USERS:
        status, body = login(email, password)
        if status == 200:
            token = body["access_token"]
            tokens[role] = token
            save_token(role, token, email)  # write/refresh .tokens.json for this role
            print(f"  [ok] {role:9} token: {token[:32]}... (len {len(token)})")
        else:
            print(f"  [error {status}] {email}: {body}")

    if tokens:
        print(f"\nTokens cached to {TOKEN_FILE}")
        print("The event/booking scripts now use them automatically (no -e/-p needed):")
        print("  python create_event.py --title Demo --datetime 2026-10-15T09:00:00 \\")
        print("      --venue Delhi --tickets 100 --price 999.00")
        print("  python browse_events.py")
        print("  python book_ticket.py book --event-id 1 --quantity 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
