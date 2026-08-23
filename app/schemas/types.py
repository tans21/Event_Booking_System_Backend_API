from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

# India Standard Time (UTC+05:30, no daylight saving). Datetimes are stored as
# UTC instants in the database and converted to IST only at the API boundary.
IST = timezone(timedelta(hours=5, minutes=30))


def _to_ist_seconds(dt: datetime) -> str:
    """Render a datetime in IST as ISO-8601 to whole seconds, no timezone suffix."""
    if dt.tzinfo is None:
        # Naive values coming from the DB are UTC.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%Y-%m-%dT%H:%M:%S")


def normalize_datetime(value: datetime | None) -> datetime | None:
    """Coerce an inbound datetime to a UTC instant and drop sub-second precision.

    A naive ``event_datetime`` (no offset) is interpreted as IST wall-clock, then
    stored as UTC. So ``2026-10-15T09:00:00`` (9 AM IST) is persisted as the
    matching UTC instant and rendered back as ``2026-10-15T09:00:00`` IST.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(timezone.utc).replace(microsecond=0)


# Output type: renders datetimes as IST "YYYY-MM-DDTHH:MM:SS" in JSON responses.
SecondsDateTime = Annotated[
    datetime,
    PlainSerializer(_to_ist_seconds, return_type=str, when_used="json"),
]
