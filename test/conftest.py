from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock

import pytest
import jwt
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Configure before importing the application; never use developer credentials.
os.environ.update({
    "DB_DRIVER": "mysql+pymysql",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "1",
    "DB_USER": "test_only",
    "DB_PASS": "test_only",
    "DB_NAME": "test_only",
    "JWT_SECRET": "test-suite-signing-key-at-least-32-bytes",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "15",
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS": "7",
    "CORS_ORIGINS": '[]',
})

from src.core.database import engine, get_session
from src.core.dependencies import get_current_user, get_equip_serv, get_user_serv
from src.core.settings import get_settings
from src.main import app
from src.models.models import Category, Equipment, Loan, Role, RoleName, User
from src.services.equipments import EquipmentService
from src.services.users import UserService

TEST_JWT_KEY = "loan-permissions-test-secret-at-least-32-bytes"


@pytest.fixture
def auth_headers():
    def headers(user_id: int, *, expired: bool = False):
        expires = datetime.now(timezone.utc) + timedelta(minutes=-1 if expired else 15)
        token = jwt.encode(
            {"sub": str(user_id), "exp": expires}, TEST_JWT_KEY, algorithm="HS256"
        )
        return {"Authorization": f"Bearer {token}"}

    return headers


@pytest.fixture
def api_context():
    """Real routes/services/repositories, isolated SQLite database per test."""
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        for role_id, name in enumerate(RoleName, start=1):
            session.add(Role(id=role_id, name=name, description=name.value))
        session.flush()
        # Students: 1/2; manager: 3; administrator: 4.
        for user_id, role_id in [(1, 3), (2, 3), (3, 2), (4, 1)]:
            session.add(User(
                id=user_id, name=f"User {user_id}", email=f"user{user_id}@example.com",
                phone=f"1199999999{user_id}", active=True, role_id=role_id,
                pass_hash="unused",
            ))
        session.add(Category(id=1, name="Computers", description="Computers"))
        session.flush()
        session.add(Equipment(id=1, name="Notebook", code="NB-1", category_id=1))
        session.flush()
        now = datetime.now(timezone.utc)
        for user_id in range(1, 5):
            session.add(Loan(
                id=user_id, requested_by=user_id, pickup_date=now,
                due_date=now + timedelta(days=1),
            ))
        session.commit()

    def test_session():
        with Session(test_engine) as session:
            yield session

    settings = get_settings().model_copy(update={
        "jwt_secret": SecretStr(TEST_JWT_KEY), "jwt_algorithm": "HS256",
    })
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, test_engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        test_engine.dispose()


@pytest.fixture(autouse=True)
def forbid_application_database():
    """Tests must override persistence or use their own in-memory engine."""
    def deny_connection(*args, **kwargs):
        raise AssertionError("Tests must not connect to the application database")

    event.listen(engine, "do_connect", deny_connection)
    try:
        yield
    finally:
        event.remove(engine, "do_connect", deny_connection)


@pytest.fixture
def user_service() -> MagicMock:
    return MagicMock(spec=UserService)


@pytest.fixture
def equipment_service() -> MagicMock:
    return MagicMock(spec=EquipmentService)


@pytest.fixture
def client(
    user_service: MagicMock,
    equipment_service: MagicMock,
) -> Generator[TestClient, None, None]:
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_user_serv] = lambda: user_service
    app.dependency_overrides[get_equip_serv] = lambda: equipment_service

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def operator_client(client: TestClient) -> Generator[TestClient, None, None]:
    user = User(
        id=10, name="Test Manager", email="manager@example.com", phone="11999999999",
        active=True, role_id=2, pass_hash="unused",
        role=Role(id=2, name=RoleName.GESTOR, description="Manager"),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
