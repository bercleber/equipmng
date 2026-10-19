from collections.abc import Sequence

from src.models.models import Category, Equipment
from src.repositories.equipments import EquipmentRepository
from src.repositories.exceptions import DuplicateEntityError, EntityReferencedError, MissingReferenceError
from src.schemas.equipments import CategoryCreate, EquipmentCreate
from src.services.exceptions import (
    CategoryAlreadyExistsError,
    CategoryInUseError,
    CategoryNotFoundError,
    EquipmentAlreadyExistsError,
    EquipmentNotFoundError,
)


class EquipmentService:
    def __init__(self, repo: EquipmentRepository) -> None:
        self.repo = repo

    def create_category(self, category: CategoryCreate) -> Category:
        new_category = Category.model_validate(category)
        try:
            return self.repo.save_category(new_category)
        except DuplicateEntityError as err:
            raise CategoryAlreadyExistsError(new_category.name) from err

    def list_categories(self) -> Sequence[Category]:
        return self.repo.find_all_categories()

    def remove_category(self, id: int):
        category = self.repo.find_category_by_id(id)
        if category is None:
            raise CategoryNotFoundError(id)

        try:
            self.repo.delete_category(category)
        except EntityReferencedError as err:
            raise CategoryInUseError(category.name) from err

    def create(self, equipment: EquipmentCreate) -> Equipment:
        if self.repo.find_category_by_id(equipment.category_id) is None:
            raise CategoryNotFoundError(equipment.category_id)
        new_equip = Equipment.model_validate(equipment)
        try:
            return self.repo.save(new_equip)
        except DuplicateEntityError as err:
            raise EquipmentAlreadyExistsError(new_equip.code) from err
        except MissingReferenceError as err:
            raise CategoryNotFoundError(equipment.category_id) from err

    def list(
        self, active: bool | None = None, available: bool | None = None
    ) -> Sequence[Equipment]:
        return self.repo.list(active, available)

    def remove(self, id: int) -> Equipment:
        equip = self.repo.find_by_id(id)
        if equip is None:
            raise EquipmentNotFoundError(id)

        equip.active = False
        return self.repo.save(equip)
