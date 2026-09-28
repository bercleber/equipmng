from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, status

from src.core.dependencies import EquipmentServiceDep
from src.models.models import Category
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

router = APIRouter(prefix="/equipments", tags=["equipments"])


@router.get(
    "",
    response_model=list[EquipmentRead],
    status_code=status.HTTP_200_OK,
)
def list(serv: EquipmentServiceDep):
    return serv.list()


@router.post(
    "",
    response_model=EquipmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create(serv: EquipmentServiceDep, data: EquipmentCreate):
    try:
        return serv.create(data)
    except EquipmentAlreadyExistsError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err


@router.delete(
    "/{id}",
    status_code=status.HTTP_200_OK,
)
def delete(serv: EquipmentServiceDep, id: int):
    try:
        serv.remove(id)
    except EquipmentNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.get(
    "/categories",
    response_model=Sequence[Category],
    status_code=status.HTTP_200_OK,
)
def list_categories(serv: EquipmentServiceDep):
    return serv.list_categories()


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
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
    status_code=status.HTTP_200_OK,
)
def delete_category(serv: EquipmentServiceDep, id: int):
    try:
        serv.remove_category(id)
    except CategoryNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except CategoryInUseError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        )
