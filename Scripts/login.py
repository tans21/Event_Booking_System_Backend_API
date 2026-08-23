#!/usr/bin/env python3
"""Call POST /api/v1/auth/login.

Usage:
    python login.py --email org@example.com --password secret123
    python login.py -e org@example.com -p secret123 --token-only

--token-only prints just the access_token (handy for shell capture):
    TOKEN=$(python login.py -e org@example.com -p secret123 --token-only)

Override the server with the BASE_URL env var.
"""
from __future__ import annotations

import argparse
import json
import sys

from api_client import BASE_URL, login, save_token


def main() -> int:
    # argparse builds the command-line interface: it parses flags, enforces
    # required ones, generates `-h/--help`, and errors on bad input.
    parser = argparse.ArgumentParser(description="Log in via the auth API.")
    # Each add_argument defines one flag. "-e"/"--email" are the short/long names;
    # both default to the demo organizer so the script runs with no arguments.
    parser.add_argument("-e", "--email", default="org@example.com")
    parser.add_argument("-p", "--password", default="secret123")
    # action="store_true" makes this a boolean flag: absent -> False, present -> True.
    parser.add_argument(
        "--token-only",
        action="store_true",
        help="Print only the access token (nothing else).",
    )
    # Read sys.argv into `args`; args.email, args.password, args.token_only are now set.
    args = parser.parse_args()

    # Hit the login endpoint; returns (HTTP status code, parsed JSON body).
    status, body = login(args.email, args.password)

    # Cache the token by role so the event/booking scripts can reuse it.
    if status == 200 and "access_token" in body:
        save_token(body.get("role", ""), body["access_token"], args.email)

    if args.token_only:
        if status < 400 and "access_token" in body:
            print(body["access_token"])
            return 0
        print(f"Login failed (HTTP {status}): {body}", file=sys.stderr)
        return 1

    print(f"POST {BASE_URL}/api/v1/auth/login")
    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
