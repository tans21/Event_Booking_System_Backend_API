from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus
from app.schemas.types import SecondsDateTime


class BookingCreate(BaseModel):
    event_id: int
    quantity: int = Field(gt=0)


class EventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    venue: str
    event_datetime: SecondsDateTime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    event_id: int
    quantity: int
    total_price: Decimal = Field(examples=["1998.00"])
    status: BookingStatus
    booked_at: SecondsDateTime
    cancelled_at: SecondsDateTime | None


class BookingWithEvent(BookingOut):
    event: EventSummary


class BookingListResponse(BaseModel):
    total: int
    items: list[BookingWithEvent]
