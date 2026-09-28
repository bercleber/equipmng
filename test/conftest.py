from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.core.dependencies import get_equip_serv, get_user_serv
from src.main import app
from src.services.equipments import EquipmentService
from src.services.users import UserService


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
    app.dependency_overrides[get_user_serv] = lambda: user_service
    app.dependency_overrides[get_equip_serv] = lambda: equipment_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
