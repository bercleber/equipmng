from collections.abc import Sequence

from pwdlib import PasswordHash

from src.models.models import RoleName, User
from src.repositories.users import UserRepository
from src.repositories.exceptions import DuplicateEntityError
from src.schemas.users import UserCreate
from src.services.exceptions import (
    InvalidUserPromotionError, UserAlreadyExistsError, UserNotFoundError,
    UserPermissionDeniedError,
)


class UserService:
    def __init__(self, repo: UserRepository, hasher: PasswordHash) -> None:
        self.repo = repo
        self.hasher = hasher

    def _role_filter(self, user: User) -> RoleName | None:
        if not user.active or user.id is None or user.role is None:
            raise UserPermissionDeniedError()
        if user.role.name == RoleName.ADMINISTRADOR:
            return None
        if user.role.name == RoleName.GESTOR:
            return RoleName.ALUNO
        raise UserPermissionDeniedError()

    def _switch_status(self, id: int, active: bool, user: User) -> None:
        allowed_role = self._role_filter(user)
        db_user = self.repo.find_by_id_with_role(id, for_update=True)
        if db_user is None:
            raise UserNotFoundError(id)
        if allowed_role is not None and (
            db_user.role is None or db_user.role.name != allowed_role
        ):
            raise UserPermissionDeniedError()
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

    def list(self, user: User, active: bool | None = None) -> Sequence[User]:
        return self.repo.find_users(active, role_name=self._role_filter(user))

    def find_by_id(self, id: int, user: User) -> User:
        db_user = self.repo.find_by_id_with_role(id, role_name=self._role_filter(user))
        if db_user is None:
            raise UserNotFoundError(id)
        return db_user

    def activate(self, id: int, user: User) -> None:
        self._switch_status(id, True, user)

    def deactivate(self, id: int, user: User) -> None:
        self._switch_status(id, False, user)

    def promote(self, id: int, user: User) -> User:
        if self._role_filter(user) is not None:
            raise UserPermissionDeniedError()
        db_user = self.repo.find_by_id_with_role(id, for_update=True)
        if db_user is None:
            raise UserNotFoundError(id)
        if db_user.role.name != RoleName.ALUNO:
            raise InvalidUserPromotionError()

        role = self.repo.get_role_by_name(RoleName.GESTOR)
        db_user.role = role
        return self.repo.save(db_user)
