from datetime import date, datetime, time
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate


async def create_event(
    db: AsyncSession, organizer_id: int, data: EventCreate
) -> Event:
    event = Event(
        organizer_id=organizer_id,
        title=data.title,
        description=data.description,
        event_datetime=data.event_datetime,
        venue=data.venue,
        total_tickets=data.total_tickets,
        tickets_available=data.total_tickets,
        ticket_price=data.ticket_price,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def _get_owned_event(
    db: AsyncSession, event_id: int, organizer_id: int
) -> Event:
    event = await db.get(Event, event_id)
    if event is None or not event.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    if event.organizer_id != organizer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this event",
        )
    return event


async def update_event(
    db: AsyncSession, event_id: int, organizer_id: int, data: EventUpdate
) -> tuple[Event, list[str]]:
    event = await _get_owned_event(db, event_id, organizer_id)

    updates = data.model_dump(exclude_unset=True)
    changed_fields: list[str] = []

    if "total_tickets" in updates:
        new_total = updates["total_tickets"]
        sold = event.total_tickets - event.tickets_available
        if new_total < sold:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"total_tickets ({new_total}) cannot be less than tickets already sold ({sold})",
            )
        event.tickets_available = new_total - sold

    for field, value in updates.items():
        if getattr(event, field) != value:
            setattr(event, field, value)
            changed_fields.append(field)

    await db.commit()
    await db.refresh(event)
    return event, changed_fields


async def deactivate_event(
    db: AsyncSession, event_id: int, organizer_id: int
) -> None:
    event = await _get_owned_event(db, event_id, organizer_id)
    event.is_active = False
    await db.commit()


async def _event_stats(db: AsyncSession, event: Event) -> dict:
    result = await db.execute(
        select(
            func.coalesce(func.sum(Booking.quantity), 0),
            func.coalesce(func.sum(Booking.total_price), 0),
            func.count(Booking.id),
        ).where(
            Booking.event_id == event.id,
            Booking.status == BookingStatus.confirmed,
        )
    )
    tickets_sold, revenue, active_count = result.one()
    return {
        "tickets_sold": int(tickets_sold),
        "total_revenue": Decimal(revenue),
        "active_bookings_count": int(active_count),
    }


async def get_organizer_events_with_stats(
    db: AsyncSession, organizer_id: int, offset: int, limit: int
) -> tuple[int, list[dict]]:
    total = await db.scalar(
        select(func.count(Event.id)).where(Event.organizer_id == organizer_id)
    )
    result = await db.execute(
        select(Event)
        .where(Event.organizer_id == organizer_id)
        .order_by(Event.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = result.scalars().all()

    items: list[dict] = []
    for event in events:
        stats = await _event_stats(db, event)
        items.append({"event": event, **stats})
    return int(total or 0), items


async def get_organizer_event_with_stats(
    db: AsyncSession, event_id: int, organizer_id: int
) -> dict:
    event = await _get_owned_event(db, event_id, organizer_id)
    stats = await _event_stats(db, event)
    return {"event": event, **stats}


async def list_public_events(
    db: AsyncSession,
    *,
    q: str | None,
    date_from: date | None,
    date_to: date | None,
    venue: str | None,
    available_only: bool,
    offset: int,
    limit: int,
) -> tuple[int, list[Event]]:
    conditions = [Event.is_active.is_(True)]

    if q:
        pattern = f"%{q}%"
        conditions.append(Event.title.ilike(pattern) | Event.venue.ilike(pattern))
    if venue:
        conditions.append(Event.venue.ilike(f"%{venue}%"))
    if date_from:
        conditions.append(
            Event.event_datetime >= datetime.combine(date_from, time.min)
        )
    if date_to:
        conditions.append(
            Event.event_datetime <= datetime.combine(date_to, time.max)
        )
    if available_only:
        conditions.append(Event.tickets_available > 0)

    total = await db.scalar(select(func.count(Event.id)).where(*conditions))
    result = await db.execute(
        select(Event)
        .where(*conditions)
        .order_by(Event.event_datetime.asc())
        .offset(offset)
        .limit(limit)
    )
    return int(total or 0), list(result.scalars().all())


async def get_public_event(db: AsyncSession, event_id: int) -> Event:
    event = await db.get(Event, event_id)
    if event is None or not event.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return event
