from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.dependencies.auth import require_organizer
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventOut,
    EventStatsListResponse,
    EventUpdate,
    EventWithStats,
)
from app.services import event_service
from app.tasks.notifications import send_event_update_notifications

router = APIRouter(
    prefix="/api/v1/organizer",
    tags=["organizer"],
    dependencies=[Depends(require_organizer)],
)


@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    current_user: Annotated[User, Depends(require_organizer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await event_service.create_event(db, current_user.id, payload)


@router.get("/events", response_model=EventStatsListResponse)
async def list_my_events(
    current_user: Annotated[User, Depends(require_organizer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    total, items = await event_service.get_organizer_events_with_stats(
        db, current_user.id, offset=(page - 1) * size, limit=size
    )
    return EventStatsListResponse(
        total=total,
        items=[
            EventWithStats(
                **EventOut.model_validate(item["event"]).model_dump(),
                tickets_sold=item["tickets_sold"],
                active_bookings_count=item["active_bookings_count"],
                total_revenue=item["total_revenue"],
            )
            for item in items
        ],
    )


@router.get("/events/{event_id}", response_model=EventWithStats)
async def get_my_event(
    event_id: int,
    current_user: Annotated[User, Depends(require_organizer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    item = await event_service.get_organizer_event_with_stats(
        db, event_id, current_user.id
    )
    return EventWithStats(
        **EventOut.model_validate(item["event"]).model_dump(),
        tickets_sold=item["tickets_sold"],
        active_bookings_count=item["active_bookings_count"],
        total_revenue=item["total_revenue"],
    )


@router.put("/events/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    payload: EventUpdate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_organizer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    event, changed_fields = await event_service.update_event(
        db, event_id, current_user.id, payload
    )
    if changed_fields:
        background_tasks.add_task(
            send_event_update_notifications,
            event_id=event.id,
            event_title=event.title,
            changed_fields=changed_fields,
            session_factory=AsyncSessionLocal,
        )
    return event


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    current_user: Annotated[User, Depends(require_organizer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await event_service.deactivate_event(db, event_id, current_user.id)
    return {"message": "Event deactivated successfully"}
