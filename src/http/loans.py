from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.dependencies import CurrentUserDep, LoanServiceDep, require_roles
from src.models.models import LoanStatus, RoleName, User
from src.schemas.loans import (
    LoanApproval, LoanCreate, LoanDenial, LoanPickup, LoanRead, LoanReturn,
)
from src.services.exceptions import LoanNotFoundError, LoanPermissionDeniedError

router = APIRouter(prefix="/loans", tags=["loans"])
LoanOperatorDep = Annotated[
    User, Depends(require_roles(RoleName.GESTOR, RoleName.ADMINISTRADOR))
]


@router.get("", response_model=list[LoanRead])
def list_loans(
    serv: LoanServiceDep,
    user: CurrentUserDep,
    loan_status: LoanStatus | None = Query(default=None, alias="status"),
):
    try:
        return serv.list(user, loan_status)
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.get("/{loan_id}", response_model=LoanRead)
def find_by_id(serv: LoanServiceDep, loan_id: int, user: CurrentUserDep):
    try:
        return serv.find_by_id(loan_id, user)
    except LoanNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.post(
    "",
    response_model=LoanRead,
    status_code=status.HTTP_201_CREATED,
)
def create(serv: LoanServiceDep, data: LoanCreate, user: CurrentUserDep):
    try:
        return serv.create(data, user)
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.patch(
    "/allow/{loan_id}",
    response_model=LoanRead,
    status_code=status.HTTP_200_OK,
)
def allow(
    serv: LoanServiceDep, loan_id: int, user: LoanOperatorDep,
    data: LoanApproval | None = None,
):
    try:
        return serv.evaluate(loan_id, data or LoanApproval(), user)
    except LoanNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.patch(
    "/deny/{loan_id}",
    response_model=LoanRead,
    status_code=status.HTTP_200_OK,
)
def deny(serv: LoanServiceDep, loan_id: int, data: LoanDenial, user: LoanOperatorDep):
    try:
        return serv.evaluate(loan_id, data, user)
    except LoanNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.patch(
    "/pickup/{loan_id}",
    response_model=LoanRead,
    status_code=status.HTTP_200_OK,
)
def pickup(
    serv: LoanServiceDep, loan_id: int, user: LoanOperatorDep,
    event: LoanPickup | None = None,
):
    try:
        return serv.record(loan_id, event or LoanPickup(), user)
    except LoanNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.patch(
    "/close/{loan_id}",
    response_model=LoanRead,
    status_code=status.HTTP_200_OK,
)
def close(
    serv: LoanServiceDep, loan_id: int, user: LoanOperatorDep,
    event: LoanReturn | None = None,
):
    try:
        return serv.record(loan_id, event or LoanReturn(), user)
    except LoanNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except LoanPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err
