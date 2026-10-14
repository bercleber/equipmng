from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.core.dependencies import UserServiceDep, require_roles
from src.models.models import RoleName
from src.schemas.users import UserCreate, UserRead
from src.services.exceptions import (
    InvalidUserPromotionError, UserAlreadyExistsError, UserNotFoundError,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.patch(
    "/promote/{user_id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(RoleName.ADMINISTRADOR))],
)
def promote(serv: UserServiceDep, user_id: int):
    try:
        return serv.promote(user_id)
    except UserNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except InvalidUserPromotionError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err


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
    dependencies=[Depends(require_roles(RoleName.ADMINISTRADOR))],
)
def list(
    serv: UserServiceDep,
    active: bool | None = Query(None, description="Filtro de usuário por status"),
):
    return serv.list(active)


@router.patch(
    "/activate/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RoleName.ADMINISTRADOR))],
)
def activate(
    serv: UserServiceDep,
    user_id: int,
):
    try:
        serv.activate(user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except UserNotFoundError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.patch(
    "/deactivate/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RoleName.ADMINISTRADOR))],
)
def deactivate(
    serv: UserServiceDep,
    user_id: int,
):
    try:
        serv.deactivate(user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except UserNotFoundError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
