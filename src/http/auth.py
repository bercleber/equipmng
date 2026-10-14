from fastapi import APIRouter, HTTPException, Response, status

from src.core.dependencies import AuthServiceDep
from src.schemas.auth import LoginRequest, LoginResponse, RefreshRequest
from src.services.exceptions import (
    InactiveUserError, InvalidCredentialsError, InvalidRefreshTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(serv: AuthServiceDep, data: LoginRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        return serv.login(data)
    except InvalidCredentialsError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
    except InactiveUserError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(err),
        ) from err


@router.post("/refresh", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def refresh(serv: AuthServiceDep, data: RefreshRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        return serv.refresh(data)
    except InvalidRefreshTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
    except InactiveUserError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(err),
        ) from err
