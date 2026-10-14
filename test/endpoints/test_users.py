from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.models.models import Role, RoleName, User
from src.schemas.users import UserCreate
from src.services.exceptions import UserAlreadyExistsError


def test_create_user_success(
    client: TestClient,
    user_service: MagicMock,
) -> None:
    request_body = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "11999999999",
        "password": "secret123",
    }
    created_user = User(
        id=1,
        name=request_body["name"],
        email=request_body["email"],
        phone=request_body["phone"],
        active=False,
        role_id=1,
        role=Role(
            id=1,
            name=RoleName.ALUNO,
            description="",
        ),
        pass_hash="hashed-password",
    )
    user_service.create.return_value = created_user

    response = client.post("/users", json=request_body)

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "phone": "11999999999",
        "active": False,
        "role": {
            "id": 1,
            "name": "aluno",
        },
    }
    user_service.create.assert_called_once_with(UserCreate(**request_body))


def test_create_user_validation(
    client: TestClient,
    user_service: MagicMock,
) -> None:
    response = client.post(
        "/users",
        json={
            "name": "Test User",
            "email": "invalid-email",
            "phone": "11999999999",
            "password": "secret123",
        },
    )

    assert response.status_code == 422
    user_service.create.assert_not_called()


def test_create_user_returns_conflict_for_duplicate(
    client: TestClient,
    user_service: MagicMock,
) -> None:
    user_service.create.side_effect = UserAlreadyExistsError()

    response = client.post(
        "/users",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "11999999999",
            "password": "secret123",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A user with this email or phone already exists"}
