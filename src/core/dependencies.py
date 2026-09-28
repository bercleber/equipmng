from typing import Annotated

from fastapi import Depends
from pwdlib import PasswordHash
from sqlmodel import Session

from src.core.database import get_session
from src.core.settings import Settings, get_settings
from src.repositories.equipments import EquipmentRepository
from src.repositories.loans import LoanRepository
from src.repositories.users import UserRepository
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
