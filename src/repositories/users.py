from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import Session, select

from src.models.models import Role, RoleName, User
from src.repositories.constraints import is_duplicate
from src.repositories.exceptions import DuplicateEntityError


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_roles(self) -> Sequence[Role]:
        stmt = select(Role)
        return self.db.exec(stmt).all()

    def get_role_by_name(self, name: RoleName) -> Role:
        stmt = select(Role).where(Role.name == name)
        return self.db.exec(stmt).one()

    def save(self, user: User) -> User:
        try:
            self.db.add(user)
            self.db.commit()
            stmt = select(User).options(joinedload(User.role)).where(User.id == user.id)
            return self.db.exec(stmt).one()
        except IntegrityError as err:
            self.db.rollback()
            if is_duplicate(err):
                raise DuplicateEntityError("Email or phone already exists") from err
            raise
        except Exception:
            self.db.rollback()
            raise

    def find_users(
        self, active: bool | None = None, role_name: RoleName | None = None
    ) -> Sequence[User]:
        stmt = select(User).options(joinedload(User.role))

        if active is not None:
            stmt = stmt.where(User.active == active)
        if role_name is not None:
            stmt = stmt.where(User.role.has(Role.name == role_name))

        return self.db.exec(stmt).all()

    def find_by_id(self, id: int) -> User | None:
        stmt = select(User).where(User.id == id)
        return self.db.exec(stmt).one_or_none()

    def find_by_email(self, email: str) -> User | None:
        stmt = select(User).options(joinedload(User.role)).where(User.email == email)
        return self.db.exec(stmt).one_or_none()

    def find_by_id_with_role(
        self, id: int, *, role_name: RoleName | None = None, for_update: bool = False
    ) -> User | None:
        loader = selectinload(User.role) if for_update else joinedload(User.role)
        stmt = select(User).options(loader).where(User.id == id)
        if role_name is not None:
            stmt = stmt.where(User.role.has(Role.name == role_name))
        if for_update:
            # Lock only the user row and reload any instance cached by authentication.
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.db.exec(stmt).one_or_none()
