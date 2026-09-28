from collections.abc import Sequence

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from src.models.models import Loan, LoanStatus


class LoanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, loan: Loan):
        try:
            self.db.add(loan)
            self.db.commit()
            self.db.refresh(loan)
            return loan
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def list(self, status: LoanStatus | None) -> Sequence[Loan]:
        stmt = select(Loan)

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
                    Loan.due_date >= func.now(),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.LATE:
                stmt = stmt.where(
                    col(Loan.reviewed_by).is_not(None),
                    col(Loan.reason).is_(None),
                    col(Loan.picked_at).is_not(None),
                    Loan.due_date < func.now(),
                    col(Loan.returned_at).is_(None),
                )
            case LoanStatus.RETURNED:
                stmt = stmt.where(col(Loan.returned_at).is_not(None))

        return self.db.exec(stmt).all()

    def find_by_id(self, id: int) -> Loan | None:
        stmt = select(Loan).where(Loan.id == id)
        return self.db.exec(stmt).one_or_none()
