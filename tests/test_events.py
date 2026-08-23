"""Event API tests: organizer CRUD, RBAC, browsing/filters, stats, edge cases."""
from __future__ import annotations

from tests.conftest import auth_header, create_event

EVENTS = "/api/v1/organizer/events"
BROWSE = "/api/v1/events"


# --- create: positive -------------------------------------------------------


async def test_create_event_success(client, organizer_headers):
    body = await create_event(client, organizer_headers)
    assert body["title"] == "Tech Summit 2026"
    # tickets_available starts equal to total_tickets
    assert body["tickets_available"] == body["total_tickets"] == 100
    assert body["is_active"] is True
    assert body["event_datetime"] == "2026-10-15T09:00:00"  # IST, seconds only


async def test_create_event_zero_price_allowed(client, organizer_headers):
    body = await create_event(client, organizer_headers, ticket_price="0.00")
    assert body["ticket_price"] == "0.00"


# --- create: negative / RBAC ------------------------------------------------


async def test_create_event_as_customer_forbidden(client, customer_headers):
    resp = await client.post(EVENTS, json={}, headers=customer_headers)
    assert resp.status_code == 403


async def test_create_event_unauthenticated(client):
    resp = await client.post(EVENTS, json={})
    assert resp.status_code == 401


async def test_create_event_zero_tickets(client, organizer_headers):
    resp = await client.post(
        EVENTS, json={**_valid(), "total_tickets": 0}, headers=organizer_headers
    )
    assert resp.status_code == 422


async def test_create_event_negative_price(client, organizer_headers):
    resp = await client.post(
        EVENTS, json={**_valid(), "ticket_price": "-1.00"}, headers=organizer_headers
    )
    assert resp.status_code == 422


# --- read / stats -----------------------------------------------------------


async def test_list_my_events_with_stats(client, organizer_headers, customer_headers):
    event = await create_event(client, organizer_headers)
    # customer books 3 tickets so stats have something to report
    await client.post(
        "/api/v1/bookings",
        json={"event_id": event["id"], "quantity": 3},
        headers=customer_headers,
    )
    resp = await client.get(EVENTS, headers=organizer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["tickets_sold"] == 3
    assert item["active_bookings_count"] == 1
    assert item["total_revenue"] == "2997.00"  # 3 * 999.00


async def test_get_my_event_not_found(client, organizer_headers):
    resp = await client.get(f"{EVENTS}/9999", headers=organizer_headers)
    assert resp.status_code == 404


async def test_get_event_of_other_organizer_forbidden(client, organizer_headers):
    event = await create_event(client, organizer_headers)
    other = await auth_header(client, "org2@x.com", "secret123", "Org2", "organizer")
    resp = await client.get(f"{EVENTS}/{event['id']}", headers=other)
    assert resp.status_code == 403


# --- update -----------------------------------------------------------------


async def test_update_event_success(client, organizer_headers):
    event = await create_event(client, organizer_headers)
    resp = await client.put(
        f"{EVENTS}/{event['id']}",
        json={"venue": "New Grand Arena, Mumbai"},
        headers=organizer_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["venue"] == "New Grand Arena, Mumbai"


async def test_update_event_not_owner_forbidden(client, organizer_headers):
    event = await create_event(client, organizer_headers)
    other = await auth_header(client, "org3@x.com", "secret123", "Org3", "organizer")
    resp = await client.put(
        f"{EVENTS}/{event['id']}", json={"venue": "X"}, headers=other
    )
    assert resp.status_code == 403


async def test_update_increase_total_tickets_adjusts_available(
    client, organizer_headers, customer_headers
):
    event = await create_event(client, organizer_headers, total_tickets=10)
    await client.post(
        "/api/v1/bookings",
        json={"event_id": event["id"], "quantity": 4},
        headers=customer_headers,
    )
    # available is now 6; bump total to 20 -> available should become 16
    resp = await client.put(
        f"{EVENTS}/{event['id']}",
        json={"total_tickets": 20},
        headers=organizer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tickets"] == 20
    assert body["tickets_available"] == 16


async def test_update_reduce_total_below_sold_rejected(
    client, organizer_headers, customer_headers
):
    event = await create_event(client, organizer_headers, total_tickets=10)
    await client.post(
        "/api/v1/bookings",
        json={"event_id": event["id"], "quantity": 6},
        headers=customer_headers,
    )
    # 6 sold; try to set total to 5 -> rejected
    resp = await client.put(
        f"{EVENTS}/{event['id']}",
        json={"total_tickets": 5},
        headers=organizer_headers,
    )
    assert resp.status_code == 400


# --- delete (soft) ----------------------------------------------------------


async def test_delete_event_soft_removes_from_browse(
    client, organizer_headers, customer_headers
):
    event = await create_event(client, organizer_headers)
    resp = await client.delete(f"{EVENTS}/{event['id']}", headers=organizer_headers)
    assert resp.status_code == 200

    # no longer visible when browsing
    listing = await client.get(BROWSE, headers=customer_headers)
    assert listing.json()["total"] == 0

    # detail returns 404
    detail = await client.get(f"{BROWSE}/{event['id']}", headers=customer_headers)
    assert detail.status_code == 404


async def test_delete_event_not_owner_forbidden(client, organizer_headers):
    event = await create_event(client, organizer_headers)
    other = await auth_header(client, "org4@x.com", "secret123", "Org4", "organizer")
    resp = await client.delete(f"{EVENTS}/{event['id']}", headers=other)
    assert resp.status_code == 403


# --- browse / search / filters ----------------------------------------------


async def test_browse_available_only_excludes_soldout(
    client, organizer_headers, customer_headers
):
    sold_out = await create_event(
        client, organizer_headers, title="Sold Out", total_tickets=2
    )
    await create_event(client, organizer_headers, title="Has Seats", total_tickets=50)
    # buy all of the sold-out event
    await client.post(
        "/api/v1/bookings",
        json={"event_id": sold_out["id"], "quantity": 2},
        headers=customer_headers,
    )
    # default available_only=true hides the sold-out one
    resp = await client.get(BROWSE, headers=customer_headers)
    titles = [e["title"] for e in resp.json()["items"]]
    assert titles == ["Has Seats"]

    # available_only=false shows both
    resp_all = await client.get(
        BROWSE, params={"available_only": "false"}, headers=customer_headers
    )
    assert resp_all.json()["total"] == 2


async def test_browse_search_by_query(client, organizer_headers, customer_headers):
    await create_event(client, organizer_headers, title="Jazz Night", venue="Blue Note")
    await create_event(client, organizer_headers, title="Rock Fest", venue="Stadium")
    resp = await client.get(
        BROWSE, params={"q": "jazz"}, headers=customer_headers
    )
    assert [e["title"] for e in resp.json()["items"]] == ["Jazz Night"]


async def test_browse_filter_by_venue(client, organizer_headers, customer_headers):
    await create_event(client, organizer_headers, title="A", venue="Delhi Hall")
    await create_event(client, organizer_headers, title="B", venue="Mumbai Dome")
    resp = await client.get(
        BROWSE, params={"venue": "mumbai"}, headers=customer_headers
    )
    assert [e["title"] for e in resp.json()["items"]] == ["B"]


async def test_browse_requires_auth(client):
    resp = await client.get(BROWSE)
    assert resp.status_code == 401


async def test_get_public_event_not_found(client, customer_headers):
    resp = await client.get(f"{BROWSE}/9999", headers=customer_headers)
    assert resp.status_code == 404


def _valid() -> dict:
    from tests.conftest import VALID_EVENT

    return dict(VALID_EVENT)
