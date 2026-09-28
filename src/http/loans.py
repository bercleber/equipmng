from fastapi import APIRouter, Query, status

from src.core.dependencies import LoanServiceDep
from src.models.models import LoanStatus
from src.schemas.loans import LoanCreate, LoanEvaluate, LoanEvent, LoanRead

router = APIRouter(prefix="/loans")


@router.get("", response_model=list[LoanRead])
def list_loans(
    serv: LoanServiceDep,
    loan_status: LoanStatus | None = Query(default=None, alias="status"),
):
    return serv.list(loan_status)


@router.post(
    "",
    response_model=LoanRead,
    status_code=status.HTTP_201_CREATED,
)
def create(serv: LoanServiceDep, data: LoanCreate):
    return serv.create(data)


@router.patch(
    "/allow/{id}",
    status_code=status.HTTP_200_OK,
)
def allow(serv: LoanServiceDep, loan_id: int, data: LoanEvaluate):
    return serv.evaluate(loan_id, data)


@router.patch(
    "/deny/{id}",
    status_code=status.HTTP_200_OK,
)
def deny(serv: LoanServiceDep, loan_id: int, data: LoanEvaluate):
    return serv.evaluate(loan_id, data)


@router.patch(
    "/pickup/{id}",
    status_code=status.HTTP_200_OK,
)
def pickup(serv: LoanServiceDep, loan_id: int, event: LoanEvent):
    return serv.record(loan_id, event)


@router.patch(
    "/close/{id}",
    status_code=status.HTTP_200_OK,
)
def close(serv: LoanServiceDep, loan_id: int, event: LoanEvent):
    return serv.record(loan_id, event)
