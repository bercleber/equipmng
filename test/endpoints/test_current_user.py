from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from src.core.dependencies import CurrentUserDep, get_user_repo, require_roles
from src.core.settings import get_settings
from src.models.models import Role, RoleName, User
from src.repositories.users import UserRepository

KEY = "current-user-test-key-at-least-32-bytes"


def make_token(**overrides):
    payload = {
        "sub": "7",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    payload.update(overrides)
    return jwt.encode(payload, KEY, algorithm="HS256")


@pytest.fixture
def protected_context():
    app = FastAPI()

    @app.get("/me")
    def me(user: CurrentUserDep):
        return {"id": user.id, "role": user.role.name}

    @app.get("/admin", dependencies=[Depends(require_roles(RoleName.ADMINISTRADOR))])
    def admin():
        return {"ok": True}

    role = Role(id=3, name=RoleName.ALUNO, description="Student")
    user = User(
        id=7, name="Test User", email="test@example.com", phone="11999999999",
        active=True, role_id=3, role=role, pass_hash="unused",
    )
    repo = MagicMock(spec=UserRepository)
    repo.find_by_id_with_role.return_value = user
    settings = get_settings().model_copy(update={
        "jwt_secret": SecretStr(KEY), "jwt_algorithm": "HS256",
    })
    app.dependency_overrides[get_user_repo] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client, repo, user


@pytest.mark.parametrize("authorization", [None, "Bearer", "Basic abc", "Bearer malformed"])
def test_missing_or_malformed_token(protected_context, authorization):
    client, repo, _ = protected_context
    headers = {"Authorization": authorization} if authorization else {}
    response = client.get("/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    repo.find_by_id_with_role.assert_not_called()


@pytest.mark.parametrize("case", [
    "expired", "signature", "algorithm", "missing_sub", "missing_exp",
    "invalid_sub", "numeric_sub", "negative_sub", "invalid_exp", "refresh_type",
])
def test_invalid_claims_or_signature(protected_context, case):
    client, repo, _ = protected_context
    payload = {"sub": "7", "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}
    key, algorithm = KEY, "HS256"
    if case == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    elif case == "signature":
        key = "different-signing-key-at-least-32-bytes"
    elif case == "algorithm":
        algorithm = "HS384"
        key = KEY * 2
    elif case.startswith("missing_"):
        del payload[case.removeprefix("missing_")]
    elif case == "invalid_sub":
        payload["sub"] = "not-an-id"
    elif case == "numeric_sub":
        payload["sub"] = 7
    elif case == "negative_sub":
        payload["sub"] = "-7"
    elif case == "invalid_exp":
        payload["exp"] = []
    elif case == "refresh_type":
        payload["type"] = "refresh"
    token = jwt.encode(payload, key, algorithm=algorithm)
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    repo.find_by_id_with_role.assert_not_called()


def test_authenticated_user_and_current_permissions(protected_context):
    client, repo, user = protected_context
    headers = {"Authorization": f"Bearer {make_token()}"}
    response = client.get("/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"id": 7, "role": "aluno"}
    repo.find_by_id_with_role.assert_called_once_with(7)
    assert client.get("/admin", headers=headers).status_code == 403
    user.role.name = RoleName.ADMINISTRADOR
    assert client.get("/admin", headers=headers).status_code == 200
    user.active = False
    assert client.get("/me", headers=headers).status_code == 403


def test_deleted_user(protected_context):
    client, repo, _ = protected_context
    repo.find_by_id_with_role.return_value = None
    response = client.get("/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_repository_loads_role_before_session_closes():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            role = Role(name=RoleName.ALUNO, description="Student")
            user = User(
                name="Test User", email="test@example.com", phone="11999999999",
                active=True, role=role, pass_hash="unused",
            )
            session.add(user)
            session.commit()
            user_id = user.id
        with Session(engine) as session:
            repo = UserRepository(session)
            loaded = repo.find_by_id_with_role(user_id)
            assert loaded is not None
            assert "role" not in inspect(loaded).unloaded
            assert repo.find_by_id_with_role(999) is None
        assert loaded.role.name == RoleName.ALUNO
    finally:
        engine.dispose()
