"""Tiny dependency-free HTTP helper for the Event Booking System auth scripts.

Uses only the Python standard library (urllib), so it runs with any Python 3
interpreter without installing requests/httpx.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

# Where login tokens are cached, keyed by role. Lives next to these scripts so it
# is found regardless of the current working directory.
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tokens.json")


def post_json(path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    """POST `payload` as JSON to BASE_URL+path. Returns (status_code, response_json)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not reach {url} — is the server running?\n  {exc.reason}"
        )


def put_json(path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    """PUT `payload` as JSON to BASE_URL+path. Returns (status_code, response_json)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not reach {url} — is the server running?\n  {exc.reason}"
        )


def get_json(path: str, token: str | None = None) -> tuple[int, dict]:
    """GET BASE_URL+path. Returns (status_code, response_json)."""
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not reach {url} — is the server running?\n  {exc.reason}"
        )


def delete(path: str, token: str | None = None) -> tuple[int, dict]:
    """DELETE BASE_URL+path. Returns (status_code, response_json)."""
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not reach {url} — is the server running?\n  {exc.reason}"
        )


def register(email: str, password: str, full_name: str, role: str) -> tuple[int, dict]:
    return post_json(
        "/api/v1/auth/register",
        {"email": email, "password": password, "full_name": full_name, "role": role},
    )


def login(email: str, password: str) -> tuple[int, dict]:
    return post_json("/api/v1/auth/login", {"email": email, "password": password})


def login_or_exit(email: str, password: str) -> str:
    """Log in, cache the token by role, and return it (or exit with an error)."""
    status, body = login(email, password)
    if status == 200 and "access_token" in body:
        save_token(body.get("role", ""), body["access_token"], email)
        return body["access_token"]
    raise SystemExit(f"Login failed for {email} (HTTP {status}): {body}")


# --- token cache (.tokens.json) --------------------------------------------


def _read_tokens() -> dict:
    try:
        with open(TOKEN_FILE) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_token(role: str, token: str, email: str | None = None) -> None:
    """Create/update .tokens.json, storing this role's token without disturbing others."""
    data = _read_tokens()
    data[role] = {"token": token, "email": email}
    with open(TOKEN_FILE, "w") as fh:
        json.dump(data, fh, indent=2)


def load_token(role: str) -> str | None:
    entry = _read_tokens().get(role)
    return entry.get("token") if entry else None


def token_for(role: str, email: str | None = None, password: str | None = None) -> str:
    """Resolve a token for `role`.

    If email+password are given, log in (and cache the token). Otherwise use the
    cached token for that role. Exits with a helpful message if neither works.
    """
    if email and password:
        return login_or_exit(email, password)
    cached = load_token(role)
    if cached:
        return cached
    raise SystemExit(
        f"No cached '{role}' token found in {TOKEN_FILE}.\n"
        f"Run `python auth_demo.py` first, or pass --email/--password to log in."
    )
