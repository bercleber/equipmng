from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.core.dependencies import EquipmentServiceDep, get_current_user, require_roles
from src.models.models import RoleName
from src.schemas.equipments import (
    CategoryCreate,
    CategoryRead,
    EquipmentCreate,
    EquipmentRead,
)
from src.services.exceptions import (
    CategoryAlreadyExistsError,
    CategoryInUseError,
    CategoryNotFoundError,
    EquipmentAlreadyExistsError,
    EquipmentNotFoundError,
)

router = APIRouter(
    prefix="/equipments", tags=["equipments"],
    dependencies=[Depends(get_current_user)],
)
admin = Depends(require_roles(RoleName.ADMINISTRADOR))


@router.get(
    "",
    response_model=list[EquipmentRead],
    status_code=status.HTTP_200_OK,
)
def list_equipments(
    serv: EquipmentServiceDep,
    active: bool | None = None,
    available: bool | None = Query(
        None, description="Disponível: ativo e sem empréstimo em aberto, independentemente das datas"
    ),
):
    return serv.list(active, available)


@router.post(
    "",
    response_model=EquipmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[admin],
)
def create(serv: EquipmentServiceDep, data: EquipmentCreate):
    try:
        return serv.create(data)
    except EquipmentAlreadyExistsError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err
    except CategoryNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[admin],
)
def delete(serv: EquipmentServiceDep, id: int):
    try:
        serv.remove(id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except EquipmentNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.get(
    "/categories",
    response_model=list[CategoryRead],
    status_code=status.HTTP_200_OK,
)
def list_categories(serv: EquipmentServiceDep):
    return serv.list_categories()


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[admin],
)
def create_category(serv: EquipmentServiceDep, data: CategoryCreate):
    try:
        return serv.create_category(data)
    except CategoryAlreadyExistsError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err


@router.delete(
    "/categories/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[admin],
)
def delete_category(serv: EquipmentServiceDep, id: int):
    try:
        serv.remove_category(id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CategoryNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except CategoryInUseError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err
