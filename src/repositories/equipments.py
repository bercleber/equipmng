from collections.abc import Sequence

from sqlalchemy import and_, delete, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlmodel import Session, col, select

from src.models.models import Category, Equipment, Loan, LoanEquipmentLink
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

    @staticmethod
    def _blocking_loan_conditions():
        # Returned and denied loans do not reserve equipment. Dates do not matter.
        return (
            col(Loan.returned_at).is_(None),
            or_(col(Loan.reviewed_by).is_(None), col(Loan.reason).is_(None)),
        )

    def list(
        self, active: bool | None = None, available: bool | None = None
    ) -> Sequence[Equipment]:
        stmt = select(Equipment).options(joinedload(Equipment.category))
        if active is not None:
            stmt = stmt.where(Equipment.active == active)
        if available is not None:
            blocking_loan = (
                select(LoanEquipmentLink.loan_id)
                .join(Loan, Loan.id == LoanEquipmentLink.loan_id)
                .where(
                    LoanEquipmentLink.equipment_id == Equipment.id,
                    *self._blocking_loan_conditions(),
                )
                .exists()
            )
            is_available = and_(col(Equipment.active).is_(True), ~blocking_loan)
            stmt = stmt.where(is_available if available else ~is_available)
        return self.db.exec(stmt).all()

    def lock_by_ids(self, ids: Sequence[int]) -> Sequence[Equipment]:
        if not ids:
            return []
        try:
            stmt = (
                select(Equipment)
                .where(col(Equipment.id).in_(ids))
                .order_by(Equipment.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            return self.db.exec(stmt).all()
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError("Could not lock equipment") from err

    def find_conflicting_ids(
        self, ids: Sequence[int], *, exclude_loan_id: int | None = None
    ) -> set[int]:
        """Call after lock_by_ids, in the same transaction as the loan write."""
        if not ids:
            return set()
        try:
            stmt = (
                select(LoanEquipmentLink.equipment_id)
                .join(Loan, Loan.id == LoanEquipmentLink.loan_id)
                .where(
                    col(LoanEquipmentLink.equipment_id).in_(ids),
                    *self._blocking_loan_conditions(),
                )
            )
            if exclude_loan_id is not None:
                stmt = stmt.where(Loan.id != exclude_loan_id)
            # A locking read sees current committed rows, not the snapshot taken
            # by authentication under MySQL REPEATABLE READ.
            return set(self.db.exec(stmt.with_for_update()).all())
        except SQLAlchemyError as err:
            self.db.rollback()
            raise RepositoryError("Could not check equipment availability") from err

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
