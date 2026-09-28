from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from src.models.models import LoanStatus


class LoanCreate(BaseModel):
    requested_by: int = Field(gt=0)
    pickup_date: datetime
    due_date: datetime
    equipments: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates(self) -> "LoanCreate":
        if self.pickup_date >= self.due_date:
            raise ValueError("pickup_date must be before due_date")

        return self


class LoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_date: datetime
    requested_by: int
    reviewed_by: int | None
    pickup_date: datetime
    picked_at: datetime | None
    due_date: datetime
    returned_at: datetime | None
    reason: str | None

    @computed_field
    @property
    def status(self) -> LoanStatus:
        if self.returned_at is not None:
            return LoanStatus.RETURNED

        if self.reviewed_by is not None and self.reason is not None:
            return LoanStatus.DENIED

        if self.reviewed_by is None:
            return LoanStatus.WAITING_REVISION

        if self.picked_at is None:
            return LoanStatus.WAITING_PICKUP

        due_date = self.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)

        if due_date < datetime.now(timezone.utc):
            return LoanStatus.LATE

        return LoanStatus.ON_LOAN


class LoanEvaluateType(StrEnum):
    ACCEPTED = "accepted"
    DENIED = "denied"


class LoanEvaluate(BaseModel):
    type: LoanEvaluateType
    reason: str | None


class LoanEventType(StrEnum):
    PICKED_UP = "picked_up"
    RETURNED = "returned"


class LoanEvent(BaseModel):
    type: LoanEventType
