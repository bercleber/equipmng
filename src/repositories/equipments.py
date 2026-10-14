from collections.abc import Sequence

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlmodel import Session, col, select

from src.models.models import Category, Equipment
from src.repositories.constraints import is_duplicate, is_missing_reference, is_referenced
from src.repositories.exceptions import (
    DuplicateEntityError,
    EntityReferencedError,
    MissingReferenceError,
    RepositoryError,
)


class EquipmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_category_by_name(self, name: str) -> Category | None:
        stmt = select(Category).where(Category.name == name)
        return self.db.exec(stmt).one_or_none()

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
            if is_duplicate(err):
                raise DuplicateEntityError("Category already exists") from err
            raise RepositoryError("Could not save category") from err
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError("Could not save category") from err

    def delete_category(self, category: Category):
        try:
            self.db.exec(delete(Category).where(Category.id == category.id))
            self.db.commit()
        except IntegrityError as err:
            self.db.rollback()
            if is_referenced(err):
                raise EntityReferencedError("Category is being used") from err
            raise RepositoryError("Could not delete category") from err
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError("Could not delete category") from err

    def find_all_categories(self) -> Sequence[Category]:
        stmt = select(Category)
        return self.db.exec(stmt).all()

    def save(self, equipment: Equipment) -> Equipment:
        try:
            self.db.add(equipment)
            self.db.commit()
            self.db.refresh(equipment)
            stmt = select(Equipment).options(joinedload(Equipment.category)).where(
                Equipment.id == equipment.id
            )
            return self.db.exec(stmt).one()
        except IntegrityError as err:
            self.db.rollback()
            if is_duplicate(err):
                raise DuplicateEntityError("Equipment code already exists") from err
            if is_missing_reference(err):
                raise MissingReferenceError("Category does not exist") from err
            raise RepositoryError("Could not save equipment") from err
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError("Could not save equipment") from err

    def list(self, active: bool | None = None) -> Sequence[Equipment]:
        stmt = select(Equipment).options(joinedload(Equipment.category))
        if active is not None:
            stmt = stmt.where(Equipment.active == active)
        return self.db.exec(stmt).all()

    def find_by_id(self, id: int) -> Equipment | None:
        stmt = select(Equipment).options(joinedload(Equipment.category)).where(
            Equipment.id == id
        )
        return self.db.exec(stmt).one_or_none()

    def find_by_ids(self, ids: Sequence[int]) -> Sequence[Equipment]:
        stmt = select(Equipment).where(
            col(Equipment.id).in_(ids),
            col(Equipment.active).is_(True),
        )
        return self.db.exec(stmt).all()
