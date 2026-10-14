from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from src.core.dates import database_datetime, utc_now
from src.models.models import Equipment, Loan, LoanStatus, User


class LoanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, loan: Loan) -> Loan:
        try:
            self.db.add(loan)
            self.db.commit()
            self.db.refresh(loan)
            stmt = select(Loan).options(
                selectinload(Loan.equipments).joinedload(Equipment.category),
                selectinload(Loan.requester).load_only(User.id, User.name),
            ).where(Loan.id == loan.id)
            return self.db.exec(stmt).one()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def list(
        self, status: LoanStatus | None, requested_by: int | None = None
    ) -> Sequence[Loan]:
        stmt = select(Loan).options(
            selectinload(Loan.equipments).joinedload(Equipment.category),
            selectinload(Loan.requester).load_only(User.id, User.name),
        )
        if requested_by is not None:
            stmt = stmt.where(Loan.requested_by == requested_by)

        match status:
            case LoanStatus.WAITING_REVISION:
                stmt = stmt.where(
                    col(Loan.reviewed_by).is_(None),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.WAITING_PICKUP:
                stmt = stmt.where(
                    col(Loan.reviewed_by).is_not(None),
                    col(Loan.picked_at).is_(None),
                    col(Loan.reason).is_(None),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.DENIED:
                stmt = stmt.where(
                    col(Loan.reviewed_by).is_not(None),
                    col(Loan.reason).is_not(None),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.ON_LOAN:
                stmt = stmt.where(
                    col(Loan.reviewed_by).is_not(None),
                    col(Loan.reason).is_(None),
                    col(Loan.picked_at).is_not(None),
                    Loan.due_date >= database_datetime(utc_now()),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.LATE:
                stmt = stmt.where(
                    col(Loan.reviewed_by).is_not(None),
                    col(Loan.reason).is_(None),
                    col(Loan.picked_at).is_not(None),
                    Loan.due_date < database_datetime(utc_now()),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.RETURNED:
                stmt = stmt.where(col(Loan.returned_at).is_not(None))

        return self.db.exec(stmt).all()

    def find_by_id(
        self, id: int, requested_by: int | None = None, *, for_update: bool = False
    ) -> Loan | None:
        stmt = select(Loan).options(
            selectinload(Loan.equipments).joinedload(Equipment.category),
            selectinload(Loan.requester).load_only(User.id, User.name),
        ).where(Loan.id == id)
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        if requested_by is not None:
            stmt = stmt.where(Loan.requested_by == requested_by)
        return self.db.exec(stmt).one_or_none()
