from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingStatus
from app.models.event import Event


async def create_booking(
    db: AsyncSession, customer_id: int, event_id: int, quantity: int
) -> Booking:
    # Lock the event row to serialize concurrent bookings against the same event.
    result = await db.execute(
        select(Event).where(Event.id == event_id).with_for_update()
    )
    event = result.scalar_one_or_none()

    if event is None or not event.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    if event.tickets_available < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough tickets available (requested {quantity}, available {event.tickets_available})",
        )

    event.tickets_available -= quantity
    booking = Booking(
        customer_id=customer_id,
        event_id=event_id,
        quantity=quantity,
        total_price=event.ticket_price * quantity,
        status=BookingStatus.confirmed,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking, attribute_names=["id", "total_price", "booked_at"])
    return booking


async def list_customer_bookings(
    db: AsyncSession,
    customer_id: int,
    status_filter: BookingStatus | None,
    offset: int,
    limit: int,
) -> tuple[int, list[Booking]]:
    conditions = [Booking.customer_id == customer_id]
    if status_filter is not None:
        conditions.append(Booking.status == status_filter)

    total = await db.scalar(select(func.count(Booking.id)).where(*conditions))
    result = await db.execute(
        select(Booking)
        .where(*conditions)
        .options(selectinload(Booking.event))
        .order_by(Booking.booked_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return int(total or 0), list(result.scalars().all())


async def get_customer_booking(
    db: AsyncSession, booking_id: int, customer_id: int
) -> Booking:
    result = await db.execute(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(selectinload(Booking.event))
    )
    booking = result.scalar_one_or_none()
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )
    if booking.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this booking",
        )
    return booking


async def cancel_booking(
    db: AsyncSession, booking_id: int, customer_id: int
) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )
    if booking.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this booking",
        )
    if booking.status == BookingStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is already cancelled",
        )

    # Lock the event row before restoring inventory.
    result = await db.execute(
        select(Event).where(Event.id == booking.event_id).with_for_update()
    )
    event = result.scalar_one_or_none()

    booking.status = BookingStatus.cancelled
    booking.cancelled_at = datetime.now(timezone.utc)
    if event is not None:
        event.tickets_available += booking.quantity

    await db.commit()
    await db.refresh(booking)
    return booking
