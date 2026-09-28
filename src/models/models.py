from datetime import datetime, timezone
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel

# Base


class SQLMBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)


# Loan Equipment Relationship


class LoanEquipmentLink(SQLModel, table=True):
    __tablename__ = "loan_equipment"
    loan_id: int = Field(foreign_key="loan.id", primary_key=True)
    equipment_id: int = Field(foreign_key="equipment.id", primary_key=True)


# Role


class RoleName(StrEnum):
    ADMINISTRADOR = "administrador"
    GESTOR = "gestor"
    ALUNO = "aluno"


class Role(SQLMBase, table=True):
    name: RoleName = Field(max_length=14, unique=True)
    description: str = Field(max_length=300)

    users: list["User"] = Relationship(back_populates="role")


# User


class User(SQLMBase, table=True):
    name: str = Field(max_length=50)
    email: str = Field(max_length=40, unique=True)
    phone: str = Field(max_length=12, unique=True)
    active: bool = Field(default=False)
    role_id: int = Field(foreign_key="role.id")
    pass_hash: str = Field(max_length=255)

    role: Role = Relationship(back_populates="users")
    loans: list["Loan"] = Relationship(
        back_populates="requester",
        sa_relationship_kwargs={"primaryjoin": "User.id==Loan.requested_by"},
    )
    loans_reviewed: list["Loan"] = Relationship(
        back_populates="reviewer",
        sa_relationship_kwargs={"primaryjoin": "User.id==Loan.reviewed_by"},
    )


# Category


class Category(SQLMBase, table=True):
    name: str = Field(max_length=30, unique=True)
    description: str = Field(max_length=300)

    equipments: list["Equipment"] = Relationship(back_populates="category")


# Equipment


class Equipment(SQLMBase, table=True):
    name: str = Field(max_length=50)
    code: str = Field(max_length=50, unique=True)
    active: bool = Field(default=True)
    category_id: int = Field(foreign_key="category.id")

    category: Category = Relationship(back_populates="equipments")
    loans: list["Loan"] = Relationship(
        back_populates="equipments",
        link_model=LoanEquipmentLink,
    )


# Loan


class LoanStatus(StrEnum):
    WAITING_REVISION = "waiting_rev"
    WAITING_PICKUP = "waiting_pickup"
    DENIED = "denied"
    ON_LOAN = "on_loan"
    LATE = "late"
    RETURNED = "returned"


class Loan(SQLMBase, table=True):
    request_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requested_by: int = Field(foreign_key="user.id")
    reviewed_by: int | None = Field(default=None, foreign_key="user.id")
    pickup_date: datetime = Field()
    picked_at: datetime | None = Field(default=None)
    due_date: datetime = Field()
    returned_at: datetime | None = Field(default=None)
    reason: str | None = Field(default=None)

    equipments: list["Equipment"] = Relationship(
        back_populates="loans", link_model=LoanEquipmentLink
    )

    requester: User = Relationship(
        back_populates="loans",
        sa_relationship_kwargs={"foreign_keys": "[Loan.requested_by]"},
    )
    reviewer: User | None = Relationship(
        back_populates="loans_reviewed",
        sa_relationship_kwargs={"foreign_keys": "[Loan.reviewed_by]"},
    )
