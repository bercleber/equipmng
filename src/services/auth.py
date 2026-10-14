from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from src.core.dates import as_utc, database_datetime, utc_now
from src.core.settings import Settings
from src.models.models import RefreshSession, RefreshToken, User
from src.repositories.auth import AuthRepository
from src.repositories.users import UserRepository
from src.schemas.auth import LoginRequest, LoginResponse, RefreshRequest
from src.services.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    # Verify a hash even for unknown emails to reduce timing differences.
    return PasswordHash.recommended().hash("dummy-password-for-login")


class AuthService:
    def __init__(
        self,
        repo: UserRepository,
        hasher: PasswordHash,
        settings: Settings,
        auth_repo: AuthRepository,
    ) -> None:
        self.repo = repo
        self.hasher = hasher
        self.settings = settings
        self.auth_repo = auth_repo

    def login(self, data: LoginRequest) -> LoginResponse:
        user = self.repo.find_by_email(data.email)
        password_hash = user.pass_hash if user is not None else _dummy_password_hash()
        valid_password = self.hasher.verify(
            data.password.get_secret_value(), password_hash
        )

        if user is None or not valid_password:
            raise InvalidCredentialsError()

        if not user.active:
            raise InactiveUserError()

        now = utc_now().replace(microsecond=0)
        expires_at = now + timedelta(days=self.settings.jwt_refresh_token_expire_days)
        session_id = uuid4().hex
        refresh_token = token_urlsafe(32)
        response = self._tokens(user, refresh_token, expires_at, now)
        self.auth_repo.create_session(
            RefreshSession(
                id=session_id,
                user_id=user.id,
                created_at=database_datetime(now),
                expires_at=database_datetime(expires_at),
            ),
            RefreshToken(
                token_hash=self._digest(refresh_token),
                session_id=session_id,
            ),
        )
        return response

    def refresh(self, data: RefreshRequest) -> LoginResponse:
        found = self.auth_repo.find_for_update(
            self._digest(data.refresh_token.get_secret_value())
        )
        if found is None:
            raise InvalidRefreshTokenError()
        session, previous = found
        # Take the timestamp after acquiring the lock, not before waiting for it.
        now = utc_now()
        if session.revoked_at is not None:
            raise InvalidRefreshTokenError()
        if previous.used_at is not None or as_utc(session.expires_at) <= now:
            self.auth_repo.revoke(session, database_datetime(now))
            raise InvalidRefreshTokenError()

        user = self.repo.find_by_id_with_role(session.user_id)
        if user is None:
            self.auth_repo.revoke(session, database_datetime(now))
            raise InvalidRefreshTokenError()
        if not user.active:
            self.auth_repo.revoke(session, database_datetime(now))
            raise InactiveUserError()

        refresh_token = token_urlsafe(32)
        response = self._tokens(user, refresh_token, as_utc(session.expires_at), now)
        self.auth_repo.rotate(
            previous,
            RefreshToken(
                token_hash=self._digest(refresh_token),
                session_id=session.id,
            ),
            database_datetime(now),
        )
        return response

    @staticmethod
    def _digest(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def _tokens(
        self, user: User, refresh_token: str, expires_at: datetime, now: datetime
    ) -> LoginResponse:
        payload = {
            "sub": str(user.id),
            "name": user.name,
            "role": user.role.name.value,
            "iat": now,
            "exp": now
            + timedelta(minutes=self.settings.jwt_access_token_expire_minutes),
            "jti": uuid4().hex,
            "type": "access",
        }
        token = jwt.encode(
            payload,
            self.settings.jwt_secret.get_secret_value(),
            algorithm=self.settings.jwt_algorithm,
        )
        return LoginResponse(
            access_token=token,
            refresh_token=refresh_token,
            refresh_expires_at=as_utc(expires_at),
        )
