from collections.abc import Sequence
from datetime import datetime, timezone

from src.models.models import Loan, LoanStatus
from src.repositories.equipments import EquipmentRepository
from src.repositories.loans import LoanRepository
from src.schemas.loans import (
    LoanCreate,
    LoanEvaluate,
    LoanEvaluateType,
    LoanEvent,
    LoanEventType,
)
from src.services.exceptions import LoanNotFoundError


class LoanService:
    def __init__(
        self, loan_repo: LoanRepository, equip_repo: EquipmentRepository
    ) -> None:
        self.loan_repo = loan_repo
        self.equip_repo = equip_repo

    def create(self, loan: LoanCreate) -> Loan:
        equip_ids = list(set(loan.equipments))

        equips = self.equip_repo.find_by_ids(equip_ids)

        loan_data = loan.model_dump(exclude={"equipments"})
        new_loan = Loan.model_validate(loan_data)
        new_loan.equipments = list(equips)

        return self.loan_repo.save(new_loan)

    def list(self, status: LoanStatus | None = None) -> Sequence[Loan]:
        return self.loan_repo.list(status)

    def evaluate(self, id: int, eval: LoanEvaluate):
        loan = self.loan_repo.find_by_id(id)

        if loan is None:
            raise LoanNotFoundError(id)

        loan.reviewed_by = 1

        if eval.type is LoanEvaluateType.DENIED:
            loan.reason = eval.reason

        return self.loan_repo.save(loan)

    def record(self, id: int, event: LoanEvent):
        loan = self.loan_repo.find_by_id(id)

        if loan is None:
            raise LoanNotFoundError(id)

        if event.type is LoanEventType.PICKED_UP:
            loan.picked_at = datetime.now(timezone.utc)

        if event.type is LoanEventType.RETURNED:
            loan.returned_at = datetime.now(timezone.utc)

        return self.loan_repo.save(loan)
