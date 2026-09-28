from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, col, select

from src.models.models import Category, Equipment
from src.repositories.exceptions import (
    DuplicateEntityError,
    EntityReferencedError,
    RepositoryError,
)


class EquipmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_category_by_name(self, name: str) -> Category | None:
        stmt = select(Category).where(Category.name == name)
        try:
            return self.db.exec(stmt).one_or_none()
        except IntegrityError as err:
            raise DuplicateEntityError(f"Category '{name}' already exists") from err

    def find_category_by_id(self, id: int) -> Category | None:
        stmt = select(Category).where(Category.id == id)
        return self.db.exec(stmt).one_or_none()

    def save_category(self, category: Category) -> Category:
        try:
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
            return category
        except IntegrityError as err:
            self.db.rollback()
            raise DuplicateEntityError(
                f"Category '{category.name}' already exists"
            ) from err
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError(f"Could not save category '{category.name}'") from err

    def delete_category(self, category: Category):
        try:
            self.db.delete(category)
            self.db.commit()
        except IntegrityError as err:
            self.db.rollback()
            raise EntityReferencedError(
                f"Category '{category.name}' is being used"
            ) from err
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError(
                f"Could not delete category '{category.name}'"
            ) from err

    def find_all_categories(self) -> Sequence[Category]:
        stmt = select(Category)
        return self.db.exec(stmt).all()

    def save(self, equipment: Equipment) -> Equipment:
        try:
            self.db.add(equipment)
            self.db.commit()
            self.db.refresh(equipment)
            return equipment
        except IntegrityError as err:
            self.db.rollback()
            raise DuplicateEntityError(
                f"Equipment with code '{equipment.code}' already exists"
            ) from err
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError(
                f"Could not save equipment '{equipment.name}'"
            ) from err

    def list(self) -> Sequence[Equipment]:
        stmt = select(Equipment)
        return self.db.exec(stmt).all()

    def find_by_id(self, id: int) -> Equipment | None:
        stmt = select(Equipment).where(Equipment.id == id)
        return self.db.exec(stmt).one_or_none()

    def find_by_ids(self, ids: Sequence[int]) -> Sequence[Equipment]:
        stmt = select(Equipment).where(
            col(Equipment.id).in_(ids),
            col(Equipment.active).is_(True),
        )
        return self.db.exec(stmt).all()
