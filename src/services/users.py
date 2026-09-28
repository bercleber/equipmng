from collections.abc import Sequence

from pwdlib import PasswordHash

from src.models.models import RoleName, User
from src.repositories.users import UserRepository
from src.schemas.users import UserCreate


class UserService:
    def __init__(self, repo: UserRepository, hasher: PasswordHash) -> None:
        self.repo = repo
        self.hasher = hasher

    def _switch_status(self, id: int, active: bool) -> None:
        db_user = self.repo.find_by_id(id)
        db_user.sqlmodel_update({"active": active})
        self.repo.save(db_user)

    def create(self, user: UserCreate) -> User:
        role = self.repo.get_role_by_name(RoleName.ALUNO)
        pass_hash = self.hasher.hash(user.password.get_secret_value())

        new_user = User.model_validate(
            user, update={"role_id": role.id, "pass_hash": pass_hash}
        )

        return self.repo.save(new_user)

    def list(self, active: bool | None = None) -> Sequence[User]:
        return self.repo.find_users(active)

    def activate(self, id: int) -> None:
        self._switch_status(id, True)

    def deactivate(self, id: int) -> None:
        self._switch_status(id, False)
