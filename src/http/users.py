from fastapi import APIRouter, HTTPException, Query, status

from src.core.dependencies import UserServiceDep
from src.schemas.users import UserCreate, UserRead

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


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
    except Exception as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.get(
    "",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
)
def list(
    serv: UserServiceDep,
    active: bool | None = Query(None, description="Filtro de usuário por status"),
):
    try:
        return serv.list(active)
    except Exception as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.patch(
    "/activate/{user_id}",
    status_code=status.HTTP_200_OK,
)
def activate(
    serv: UserServiceDep,
    user_id: int,
):
    try:
        return serv.activate(user_id)
    except Exception as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.patch(
    "/deactivate/{user_id}",
    status_code=status.HTTP_200_OK,
)
def deactivate(
    serv: UserServiceDep,
    user_id: int,
):
    try:
        return serv.deactivate(user_id)
    except Exception as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
