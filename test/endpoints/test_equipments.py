from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.schemas.equipments import CategorySummary, EquipmentCreate, EquipmentRead
from src.services.exceptions import CategoryNotFoundError


def test_create_equipment_success(
    operator_client: TestClient,
    equipment_service: MagicMock,
) -> None:
    request_body = {
        "name": "Notebook",
        "category_id": 1,
        "code": "NB-1",
    }
    equipment_service.create.return_value = EquipmentRead(
        id=3,
        name="Notebook",
        code="NB-1",
        active=True,
        category=CategorySummary(id=1, name="Computers"),
    )

    response = operator_client.post("/equipments", json=request_body)

    assert response.status_code == 201
    assert response.json() == {
        "id": 3,
        "name": "Notebook",
        "code": "NB-1",
        "active": True,
        "category": {
            "id": 1,
            "name": "Computers",
        },
    }
    equipment_service.create.assert_called_once_with(EquipmentCreate(**request_body))


def test_create_equipment_validation_error(
    operator_client: TestClient,
    equipment_service: MagicMock,
) -> None:
    response = operator_client.post(
        "/equipments",
        json={
            "name": "Notebook",
            "category_id": 0,
            "code": "NB-1",
        },
    )

    assert response.status_code == 422
    equipment_service.create.assert_not_called()


def test_create_equipment_returns_not_found_for_missing_category(
    operator_client: TestClient,
    equipment_service: MagicMock,
) -> None:
    equipment_service.create.side_effect = CategoryNotFoundError(999)

    response = operator_client.post(
        "/equipments",
        json={
            "name": "Notebook",
            "category_id": 999,
            "code": "NB-1",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No category with 999 ID was found"}
