from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.schemas.equipments import CategorySummary, EquipmentCreate, EquipmentRead


def test_create_equipment_success(
    client: TestClient,
    equipment_service: MagicMock,
) -> None:
    request_body = {
        "name": "Notebook",
        "category_id": 1,
        "quantity": 2,
    }
    equipment_service.create.return_value = EquipmentRead(
        id=3,
        name="Notebook",
        codes=["3-1", "3-2"],
        category=CategorySummary(id=1, name="Computers"),
        quantity=2,
    )

    response = client.post("/equipments", json=request_body)

    assert response.status_code == 201
    assert response.json() == {
        "id": 3,
        "name": "Notebook",
        "codes": ["3-1", "3-2"],
        "category": {
            "id": 1,
            "name": "Computers",
        },
        "quantity": 2,
    }
    equipment_service.create.assert_called_once_with(EquipmentCreate(**request_body))


def test_create_equipment_validation_error(
    client: TestClient,
    equipment_service: MagicMock,
) -> None:
    response = client.post(
        "/equipments",
        json={
            "name": "Notebook",
            "category_id": 1,
            "quantity": 0,
        },
    )

    assert response.status_code == 422
    equipment_service.create.assert_not_called()


def test_create_equipment_returns_server_error_when_service_fails(
    client: TestClient,
    equipment_service: MagicMock,
) -> None:
    equipment_service.create.side_effect = ValueError("Category not found")

    response = client.post(
        "/equipments",
        json={
            "name": "Notebook",
            "category_id": 999,
            "quantity": 1,
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Category not found"}
