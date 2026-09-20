import logging
from decimal import Decimal
from email.message import EmailMessage

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.user import User

logger = logging.getLogger("event_booking.notifications")


def _recipient(email: str) -> str:
    # Optional demo override: redirect all mail to a single inbox.
    return settings.EMAIL_TO_OVERRIDE or email


async def _send_email(*, to: str, subject: str, html: str) -> None:
    """Send one HTML email via Gmail SMTP (STARTTLS)."""
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content("This message requires an HTML-capable email client.")
    message.add_alternative(html, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )


async def send_booking_confirmation(
    *,
    booking_id: int,
    customer_email: str,
    event_title: str,
    quantity: int,
    total_price: Decimal,
) -> None:
    """Background Task 1: send a real booking confirmation email via Gmail SMTP."""
    to = _recipient(customer_email)
    html = f"""
    <h2>Booking Confirmed!</h2>
    <p>Hi there,</p>
    <p>Your booking for <strong>{event_title}</strong> is confirmed.</p>
    <ul>
      <li><strong>Booking ID:</strong> #{booking_id}</li>
      <li><strong>Tickets:</strong> {quantity}</li>
      <li><strong>Total:</strong> ${total_price}</li>
    </ul>
    <p>Enjoy the event!</p>
    """
    try:
        await _send_email(
            to=to,
            subject=f"Booking Confirmed: {event_title}",
            html=html,
        )
        logger.info(
            "[EMAIL] Booking confirmation sent to %s — Booking #%d", to, booking_id
        )
    except Exception as exc:
        logger.error(
            "[EMAIL] Failed to send booking confirmation to %s: %s", to, exc
        )


async def send_event_update_notifications(
    *,
    event_id: int,
    event_title: str,
    changed_fields: list[str],
    session_factory: async_sessionmaker,
) -> None:
    """Background Task 2: email every customer with a confirmed booking when an event changes."""
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

    if not emails:
        logger.info(
            '[EMAIL] Event "%s" updated (%s) — no customers with active bookings to notify',
            event_title, changes,
        )
        return

    html = f"""
    <h2>Event Update: {event_title}</h2>
    <p>The following details have changed for an event you booked:</p>
    <p><strong>Updated fields:</strong> {changes}</p>
    <p>Please check the event page for the latest information.</p>
    """
    for email in emails:
        to = _recipient(email)
        try:
            await _send_email(
                to=to,
                subject=f"Event Update: {event_title}",
                html=html,
            )
            logger.info(
                '[EMAIL] Update notification sent to %s — "%s" changed: %s',
                to, event_title, changes,
            )
        except Exception as exc:
            logger.error(
                "[EMAIL] Failed to send update notification to %s: %s", to, exc
            )
