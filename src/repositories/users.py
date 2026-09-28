from collections.abc import Sequence

from sqlalchemy.orm import joinedload
from sqlmodel import Session, select

from src.models.models import Role, RoleName, User


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
        except Exception:
            self.db.rollback()
            raise

    def find_users(self, active: bool | None = None) -> Sequence[User]:
        stmt = select(User)

        if active is not None:
            stmt = stmt.where(User.active == active)

        return self.db.exec(stmt).all()

    def find_by_id(self, id: int) -> User:
        stmt = select(User).where(User.id == id)
        return self.db.exec(stmt).one()
