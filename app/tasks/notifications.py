import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.booking import Booking, BookingStatus
from app.models.user import User

logger = logging.getLogger("event_booking.notifications")


async def send_booking_confirmation(
    *,
    booking_id: int,
    customer_email: str,
    event_title: str,
    quantity: int,
    total_price: Decimal,
) -> None:
    """Background Task 1: simulate a booking confirmation email (console log)."""
    logger.info(
        '[EMAIL] Confirmation sent to %s for "%s" — %d ticket(s), $%s (Booking #%d)',
        customer_email,
        event_title,
        quantity,
        total_price,
        booking_id,
    )


async def send_event_update_notifications(
    *,
    event_id: int,
    event_title: str,
    changed_fields: list[str],
    session_factory: async_sessionmaker,
) -> None:
    """Background Task 2: notify every customer with a confirmed booking for the event.

    Opens its own DB session — the request-scoped session is already closed by the
    time this runs.
    """
    async with session_factory() as db:
        result = await db.execute(
            select(User.email)
            .join(Booking, Booking.customer_id == User.id)
            .where(
                Booking.event_id == event_id,
                Booking.status == BookingStatus.confirmed,
            )
            .distinct()
        )
        emails = result.scalars().all()

    changes = ", ".join(changed_fields) if changed_fields else "details"
    for email in emails:
        logger.info(
            '[EMAIL] Event update notification sent to %s — "%s" updated: %s',
            email,
            event_title,
            changes,
        )

    if not emails:
        logger.info(
            '[EMAIL] Event "%s" updated (%s) — no customers with active bookings to notify',
            event_title,
            changes,
        )
