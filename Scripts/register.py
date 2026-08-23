#!/usr/bin/env python3
"""Call POST /api/v1/auth/register.

Usage:
    python register.py --email org@example.com --password secret123 \
        --name "Olivia Organizer" --role organizer

    python register.py -e cust@example.com -p secret123 -n "Cara Customer" -r customer

Override the server with the BASE_URL env var, e.g.
    BASE_URL=http://localhost:9000 python register.py ...
"""
from __future__ import annotations

import argparse
import json
import sys

from api_client import BASE_URL, register


def main() -> int:
    # Define the CLI. Every flag has a demo default, so the script runs with no
    # arguments; pass a flag to override its default.
    parser = argparse.ArgumentParser(description="Register a user via the auth API.")
    parser.add_argument("-e", "--email", default="org@example.com")
    parser.add_argument("-p", "--password", default="secret123")
    parser.add_argument("-n", "--name", default="Olivia Organizer", help="Full name")
    # choices=[...] restricts the value: argparse rejects anything else with an error.
    parser.add_argument(
        "-r", "--role", default="organizer", choices=["organizer", "customer"]
    )
    args = parser.parse_args()  # parse the flags into `args`

    print(f"POST {BASE_URL}/api/v1/auth/register")
    # Call the endpoint; returns (HTTP status code, parsed JSON body).
    status, body = register(args.email, args.password, args.name, args.role)
    print(f"HTTP {status}")
    print(json.dumps(body, indent=2))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
