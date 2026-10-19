from collections.abc import Sequence

from src.core.dates import database_datetime, utc_now
from src.models.models import Equipment, Loan, LoanStatus, RoleName, User
from src.repositories.equipments import EquipmentRepository
from src.repositories.loans import LoanRepository
from src.schemas.loans import (
    LoanCreate,
    LoanEvaluate,
    LoanEvaluateType,
    LoanEvent,
    LoanEventType,
)
from src.services.exceptions import (
    InvalidLoanStateError,
    LoanEquipmentUnavailableError,
    LoanNotFoundError,
    LoanPermissionDeniedError,
)


class LoanService:
    def __init__(
        self, loan_repo: LoanRepository, equip_repo: EquipmentRepository
    ) -> None:
        self.loan_repo = loan_repo
        self.equip_repo = equip_repo

    def _requested_by_filter(self, user: User) -> int | None:
        if not user.active or user.id is None or user.role is None:
            raise LoanPermissionDeniedError()
        if user.role.name == RoleName.ALUNO:
            return user.id
        if user.role.name in (RoleName.GESTOR, RoleName.ADMINISTRADOR):
            return None
        raise LoanPermissionDeniedError()

    def _require_operator(self, user: User) -> None:
        if self._requested_by_filter(user) is not None:
            raise LoanPermissionDeniedError()

    def _require_available(
        self, ids: Sequence[int], equips: Sequence[Equipment],
        *, exclude_loan_id: int | None = None,
    ) -> None:
        unavailable = set(ids) - {equip.id for equip in equips if equip.active}
        unavailable.update(
            self.equip_repo.find_conflicting_ids(ids, exclude_loan_id=exclude_loan_id)
        )
        if unavailable:
            raise LoanEquipmentUnavailableError(sorted(unavailable))

    def _lock_loan(self, id: int) -> tuple[Loan, Sequence[Equipment]]:
        # Equipment membership cannot be edited by the API. Read it first, then
        # consistently lock equipment before the loan in every lifecycle action.
        snapshot = self.loan_repo.find_by_id(id)
        if snapshot is None:
            raise LoanNotFoundError(id)
        ids = sorted({equip.id for equip in snapshot.equipments})
        equips = self.equip_repo.lock_by_ids(ids)
        loan = self.loan_repo.find_by_id(id, for_update=True)
        if loan is None:
            raise LoanNotFoundError(id)
        return loan, equips

    def create(self, loan: LoanCreate, user: User) -> Loan:
        self._requested_by_filter(user)
        equip_ids = sorted(set(loan.equipments))
        equips = self.equip_repo.lock_by_ids(equip_ids)
        self._require_available(equip_ids, equips)

        loan_data = loan.model_dump(exclude={"equipments"})
        loan_data["pickup_date"] = database_datetime(loan.pickup_date)
        loan_data["due_date"] = database_datetime(loan.due_date)
        new_loan = Loan.model_validate(loan_data, update={"requested_by": user.id})
        new_loan.equipments = list(equips)

        return self.loan_repo.save(new_loan)

    def list(self, user: User, status: LoanStatus | None = None) -> Sequence[Loan]:
        return self.loan_repo.list(status, requested_by=self._requested_by_filter(user))

    def find_by_id(self, id: int, user: User) -> Loan:
        loan = self.loan_repo.find_by_id(
            id, requested_by=self._requested_by_filter(user)
        )

        if loan is None:
            raise LoanNotFoundError(id)
        return loan

    def evaluate(self, id: int, eval: LoanEvaluate, user: User) -> Loan:
        self._require_operator(user)
        loan, equips = self._lock_loan(id)
        if loan.picked_at is not None or loan.returned_at is not None:
            raise InvalidLoanStateError("A collected or returned loan cannot be evaluated")

        if eval.type == LoanEvaluateType.ACCEPTED:
            self._require_available(
                [equip.id for equip in equips], equips, exclude_loan_id=id
            )

        loan.reviewed_by = user.id

        loan.reason = eval.reason if eval.type == LoanEvaluateType.DENIED else None

        return self.loan_repo.save(loan)

    def record(self, id: int, event: LoanEvent, user: User) -> Loan:
        self._require_operator(user)
        loan, _ = self._lock_loan(id)
        if loan.returned_at is not None:
            raise InvalidLoanStateError("Loan was already returned")

        if event.type == LoanEventType.PICKED_UP:
            if loan.reviewed_by is None or loan.reason is not None:
                raise InvalidLoanStateError("Only approved loans can be picked up")
            if loan.picked_at is not None:
                raise InvalidLoanStateError("Loan was already picked up")
            loan.picked_at = database_datetime(utc_now())

        if event.type == LoanEventType.RETURNED:
            if loan.picked_at is None:
                raise InvalidLoanStateError("Loan has not been picked up")
            loan.returned_at = database_datetime(utc_now())

        return self.loan_repo.save(loan)
