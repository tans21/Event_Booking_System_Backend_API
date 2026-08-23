from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.types import SecondsDateTime, normalize_datetime


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Tech Summit 2026"])
    description: str | None = Field(default=None, examples=["Annual conference"])
    event_datetime: datetime = Field(examples=["2026-10-15T09:00:00"])
    venue: str = Field(
        min_length=1, max_length=300, examples=["Convention Center, Delhi"]
    )
    total_tickets: int = Field(gt=0, examples=[100])
    ticket_price: Decimal = Field(
        ge=0, max_digits=10, decimal_places=2, examples=["999.00"]
    )

    _normalize_dt = field_validator("event_datetime")(normalize_datetime)


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    event_datetime: datetime | None = Field(
        default=None, examples=["2026-10-15T09:00:00"]
    )
    venue: str | None = Field(
        default=None, min_length=1, max_length=300, examples=["New Grand Arena, Mumbai"]
    )
    total_tickets: int | None = Field(default=None, gt=0)
    ticket_price: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2, examples=["1199.00"]
    )

    _normalize_dt = field_validator("event_datetime")(normalize_datetime)


class EventOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "organizer_id": 1,
                "title": "Tech Summit 2026",
                "description": "Annual conference",
                "event_datetime": "2026-10-15T09:00:00",
                "venue": "Convention Center, Delhi",
                "total_tickets": 100,
                "tickets_available": 98,
                "ticket_price": "999.00",
                "is_active": True,
                "created_at": "2026-08-23T06:00:00",
                "updated_at": None,
            }
        },
    )

    id: int
    organizer_id: int
    title: str
    description: str | None
    event_datetime: SecondsDateTime
    venue: str
    total_tickets: int
    tickets_available: int
    ticket_price: Decimal = Field(examples=["999.00"])
    is_active: bool
    created_at: SecondsDateTime
    updated_at: SecondsDateTime | None


class EventWithStats(EventOut):
    tickets_sold: int
    active_bookings_count: int
    total_revenue: Decimal


class EventListResponse(BaseModel):
    total: int
    items: list[EventOut]


class EventStatsListResponse(BaseModel):
    total: int
    items: list[EventWithStats]
