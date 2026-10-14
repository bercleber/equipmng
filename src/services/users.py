from collections.abc import Sequence

from pwdlib import PasswordHash

from src.models.models import RoleName, User
from src.repositories.users import UserRepository
from src.repositories.exceptions import DuplicateEntityError
from src.schemas.users import UserCreate
from src.services.exceptions import (
    InvalidUserPromotionError, UserAlreadyExistsError, UserNotFoundError,
)


class UserService:
    def __init__(self, repo: UserRepository, hasher: PasswordHash) -> None:
        self.repo = repo
        self.hasher = hasher

    def _switch_status(self, id: int, active: bool) -> None:
        db_user = self.repo.find_by_id(id)
        if db_user is None:
            raise UserNotFoundError(id)
        db_user.sqlmodel_update({"active": active})
        self.repo.save(db_user)

    def create(self, user: UserCreate) -> User:
        role = self.repo.get_role_by_name(RoleName.ALUNO)
        pass_hash = self.hasher.hash(user.password.get_secret_value())

        new_user = User.model_validate(
            user, update={"role_id": role.id, "pass_hash": pass_hash}
        )

        try:
            return self.repo.save(new_user)
        except DuplicateEntityError as err:
            raise UserAlreadyExistsError() from err

    def list(self, active: bool | None = None) -> Sequence[User]:
        return self.repo.find_users(active)

    def activate(self, id: int) -> None:
        self._switch_status(id, True)

    def deactivate(self, id: int) -> None:
        self._switch_status(id, False)

    def promote(self, id: int) -> User:
        db_user = self.repo.find_by_id_with_role(id)
        if db_user is None:
            raise UserNotFoundError(id)
        if db_user.role.name != RoleName.ALUNO:
            raise InvalidUserPromotionError()

        role = self.repo.get_role_by_name(RoleName.GESTOR)
        db_user.role = role
        return self.repo.save(db_user)
