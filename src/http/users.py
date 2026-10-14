from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.core.dependencies import UserServiceDep, require_roles
from src.models.models import RoleName, User
from src.schemas.users import UserCreate, UserRead
from src.services.exceptions import (
    InvalidUserPromotionError, UserAlreadyExistsError, UserNotFoundError,
    UserPermissionDeniedError,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)
UserOperatorDep = Annotated[
    User, Depends(require_roles(RoleName.GESTOR, RoleName.ADMINISTRADOR))
]
UserAdminDep = Annotated[User, Depends(require_roles(RoleName.ADMINISTRADOR))]


@router.patch(
    "/promote/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def promote(serv: UserServiceDep, user_id: int, user: UserAdminDep):
    try:
        return serv.promote(user_id, user)
    except UserNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except InvalidUserPromotionError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err
    except UserPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    serv: UserServiceDep,
    data: UserCreate,
):
    try:
        return serv.create(data)
    except UserAlreadyExistsError as err:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err


@router.get(
    "",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
)
def list(
    serv: UserServiceDep,
    user: UserOperatorDep,
    active: bool | None = Query(None, description="Filtro de usuário por status"),
):
    try:
        return serv.list(user, active)
    except UserPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.get("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
def find_by_id(serv: UserServiceDep, user_id: int, user: UserOperatorDep):
    try:
        return serv.find_by_id(user_id, user)
    except UserNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except UserPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.patch(
    "/activate/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def activate(
    serv: UserServiceDep,
    user_id: int,
    user: UserOperatorDep,
):
    try:
        serv.activate(user_id, user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except UserNotFoundError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except UserPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err


@router.patch(
    "/deactivate/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate(
    serv: UserServiceDep,
    user_id: int,
    user: UserOperatorDep,
):
    try:
        serv.deactivate(user_id, user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except UserNotFoundError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except UserPermissionDeniedError as err:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(err)) from err
