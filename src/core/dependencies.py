from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlmodel import Session

from src.core.database import get_session
from src.core.settings import Settings, get_settings
from src.models.models import RoleName, User
from src.repositories.auth import AuthRepository
from src.repositories.equipments import EquipmentRepository
from src.repositories.loans import LoanRepository
from src.repositories.users import UserRepository
from src.services.auth import AuthService
from src.services.equipments import EquipmentService
from src.services.loans import LoanService
from src.services.users import UserService

SettingsDep = Annotated[Settings, Depends(get_settings)]

SessionDep = Annotated[Session, Depends(get_session)]

HasherDep = Annotated[PasswordHash, Depends(PasswordHash.recommended)]

# User Dependencies


def get_user_repo(db: SessionDep) -> UserRepository:
    return UserRepository(db)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repo)]


def get_user_serv(repo: UserRepositoryDep, hasher: HasherDep) -> UserService:
    return UserService(repo, hasher)


UserServiceDep = Annotated[UserService, Depends(get_user_serv)]


# Auth Dependencies


def get_auth_repo(db: SessionDep) -> AuthRepository:
    return AuthRepository(db)


AuthRepositoryDep = Annotated[AuthRepository, Depends(get_auth_repo)]


def get_auth_serv(
    repo: UserRepositoryDep, hasher: HasherDep, settings: SettingsDep,
    auth_repo: AuthRepositoryDep,
) -> AuthService:
    return AuthService(repo, hasher, settings, auth_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_serv)]

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    repo: UserRepositoryDep,
    settings: SettingsDep,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        if payload.get("type", "access") != "access":
            raise ValueError("Invalid token type")
        user_id = int(payload["sub"])
        if user_id <= 0 or str(user_id) != payload["sub"]:
            raise ValueError("Invalid subject")
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError) as err:
        raise unauthorized from err

    user = repo.find_by_id_with_role(user_id)
    if user is None:
        raise unauthorized
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: RoleName) -> Callable[..., User]:
    def check_role(user: CurrentUserDep) -> User:
        if user.role is None or user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return check_role


# Equipment Dependencies


def get_equip_repo(db: SessionDep) -> EquipmentRepository:
    return EquipmentRepository(db)


EquipmentRepositoryDep = Annotated[EquipmentRepository, Depends(get_equip_repo)]


def get_equip_serv(repo: EquipmentRepositoryDep) -> EquipmentService:
    return EquipmentService(repo)


EquipmentServiceDep = Annotated[EquipmentService, Depends(get_equip_serv)]


# Loans Dependencies


def get_loan_repo(db: SessionDep) -> LoanRepository:
    return LoanRepository(db)


LoanRepositoryDep = Annotated[LoanRepository, Depends(get_loan_repo)]


def get_loan_serv(
    loan_repo: LoanRepositoryDep, equip_repo: EquipmentRepositoryDep
) -> LoanService:
    return LoanService(loan_repo, equip_repo)


LoanServiceDep = Annotated[LoanService, Depends(get_loan_serv)]
