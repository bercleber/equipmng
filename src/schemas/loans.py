from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from src.core.dates import as_utc, utc_now
from src.models.models import LoanStatus
from src.schemas.equipments import EquipmentRead


class LoanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pickup_date: datetime
    due_date: datetime
    equipments: list[Annotated[int, Field(gt=0)]] = Field(min_length=1)

    @field_validator("pickup_date", "due_date")
    @classmethod
    def normalize_dates(cls, value: datetime) -> datetime:
        return as_utc(value)

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
    equipments: list[EquipmentRead]

    @field_validator(
        "request_date", "pickup_date", "due_date", "picked_at", "returned_at"
    )
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None

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

        if self.due_date < utc_now():
            return LoanStatus.LATE

        return LoanStatus.ON_LOAN


class LoanEvaluateType(StrEnum):
    ACCEPTED = "accepted"
    DENIED = "denied"


class LoanEvaluate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: LoanEvaluateType
    reason: str | None = None

    @model_validator(mode="after")
    def validate_reason(self) -> "LoanEvaluate":
        if self.type == LoanEvaluateType.DENIED and not self.reason:
            raise ValueError("A reason is required to deny a loan")
        if self.type == LoanEvaluateType.ACCEPTED and self.reason is not None:
            raise ValueError("An approved loan cannot have a denial reason")
        return self


class LoanApproval(LoanEvaluate):
    type: Literal[LoanEvaluateType.ACCEPTED] = LoanEvaluateType.ACCEPTED


class LoanDenial(LoanEvaluate):
    type: Literal[LoanEvaluateType.DENIED] = LoanEvaluateType.DENIED


class LoanEventType(StrEnum):
    PICKED_UP = "picked_up"
    RETURNED = "returned"


class LoanEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: LoanEventType


class LoanPickup(LoanEvent):
    type: Literal[LoanEventType.PICKED_UP] = LoanEventType.PICKED_UP


class LoanReturn(LoanEvent):
    type: Literal[LoanEventType.RETURNED] = LoanEventType.RETURNED
