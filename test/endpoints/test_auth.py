from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from pydantic import SecretStr

from src.core.dependencies import get_auth_repo, get_user_repo
from src.core.settings import get_settings
from src.main import app
from src.models.models import User
from src.repositories.auth import AuthRepository
from src.repositories.users import UserRepository


@pytest.fixture
def auth_context():
    repo = MagicMock(spec=UserRepository)
    user = User(
        id=7,
        name="Test User",
        email="test@example.com",
        phone="11999999999",
        active=True,
        role_id=3,
        pass_hash=PasswordHash.recommended().hash("secret123"),
    )
    repo.find_by_email.return_value = user
    settings = get_settings().model_copy(update={
        "jwt_algorithm": "HS256",
        "jwt_access_token_expire_minutes": 15,
    })
    # Use a dedicated signing key; tests never sign with the application's key.
    settings.jwt_secret = SecretStr("test-signing-key-at-least-32-bytes-long")
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_user_repo] = lambda: repo
    app.dependency_overrides[get_auth_repo] = lambda: MagicMock(spec=AuthRepository)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, repo, user, settings
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_login_issues_signed_token(auth_context):
    client, repo, user, settings = auth_context
    response = client.post(
        "/auth/login", json={"email": user.email, "password": "secret123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "refresh_token", "refresh_expires_at"}
    assert body["token_type"] == "bearer"
    claims = jwt.decode(
        body["access_token"],
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )
    assert claims["sub"] == str(user.id)
    assert claims["exp"] - claims["iat"] == 15 * 60
    repo.find_by_email.assert_called_once_with(user.email)


@pytest.mark.parametrize("unknown_user", [False, True])
def test_login_rejects_invalid_credentials(auth_context, unknown_user):
    client, repo, user, _ = auth_context
    if unknown_user:
        repo.find_by_email.return_value = None

    response = client.post(
        "/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_inactive_user(auth_context):
    client, _, user, _ = auth_context
    user.active = False
    response = client.post(
        "/auth/login", json={"email": user.email, "password": "secret123"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "User is inactive"}


def test_login_validates_request(auth_context):
    client, repo, _, _ = auth_context
    response = client.post(
        "/auth/login", json={"email": "invalid-email", "password": "secret123"}
    )

    assert response.status_code == 422
    repo.find_by_email.assert_not_called()
