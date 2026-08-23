from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_customer
from app.dependencies.db import get_db
from app.models.booking import BookingStatus
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingListResponse,
    BookingOut,
    BookingWithEvent,
)
from app.schemas.event import EventListResponse, EventOut
from app.services import booking_service, event_service
from app.tasks.notifications import send_booking_confirmation

router = APIRouter(prefix="/api/v1", tags=["customer"])


# --- Event browsing (any authenticated user) ---


@router.get("/events", response_model=EventListResponse)
async def browse_events(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(description="Search title and venue")] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    venue: str | None = None,
    available_only: bool = True,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    total, events = await event_service.list_public_events(
        db,
        q=q,
        date_from=date_from,
        date_to=date_to,
        venue=venue,
        available_only=available_only,
        offset=(page - 1) * size,
        limit=size,
    )
    return EventListResponse(
        total=total, items=[EventOut.model_validate(e) for e in events]
    )


@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await event_service.get_public_event(db, event_id)


# --- Bookings (customer only) ---


@router.post(
    "/bookings",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
)
async def book_tickets(
    payload: BookingCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    booking = await booking_service.create_booking(
        db, current_user.id, payload.event_id, payload.quantity
    )
    event = await event_service.get_public_event(db, payload.event_id)
    background_tasks.add_task(
        send_booking_confirmation,
        booking_id=booking.id,
        customer_email=current_user.email,
        event_title=event.title,
        quantity=booking.quantity,
        total_price=booking.total_price,
    )
    return booking


@router.get("/bookings", response_model=BookingListResponse)
async def my_bookings(
    current_user: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[
        BookingStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    total, bookings = await booking_service.list_customer_bookings(
        db, current_user.id, status_filter, offset=(page - 1) * size, limit=size
    )
    return BookingListResponse(
        total=total,
        items=[BookingWithEvent.model_validate(b) for b in bookings],
    )


@router.get("/bookings/{booking_id}", response_model=BookingWithEvent)
async def get_booking(
    booking_id: int,
    current_user: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await booking_service.get_customer_booking(
        db, booking_id, current_user.id
    )


@router.delete("/bookings/{booking_id}")
async def cancel_booking(
    booking_id: int,
    current_user: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await booking_service.cancel_booking(db, booking_id, current_user.id)
    return {"message": "Booking cancelled successfully"}
