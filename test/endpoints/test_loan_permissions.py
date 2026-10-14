from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.main import app
from src.models.models import Equipment, Loan, User
from src.repositories.equipments import EquipmentRepository
from src.repositories.loans import LoanRepository
from src.schemas.loans import LoanEvaluate, LoanEvaluateType, LoanEvent, LoanEventType
from src.services.exceptions import LoanPermissionDeniedError
from src.services.loans import LoanService


KEY = "loan-permissions-test-secret-at-least-32-bytes"


def auth(user_id):
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=15)},
        KEY, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def loan_body():
    now = datetime.now(timezone.utc)
    return {
        "pickup_date": now.isoformat(),
        "due_date": (now + timedelta(days=1)).isoformat(),
        "equipments": [1],
    }


@pytest.fixture
def loan_context(api_context):
    return api_context


@pytest.mark.parametrize("user_id", [1, 3, 4])
def test_every_role_creates_only_for_itself(loan_context, user_id):
    client, engine = loan_context
    response = client.post("/loans", json=loan_body(), headers=auth(user_id))
    assert response.status_code == 201
    body = response.json()
    assert body["requested_by"] == user_id
    assert body["reviewed_by"] is None
    assert body["status"] == "waiting_rev"
    assert body["equipments"][0]["code"] == "NB-1"
    with Session(engine) as session:
        assert session.get(Loan, body["id"]).requested_by == user_id

    spoofed = client.post(
        "/loans", json=loan_body() | {"requested_by": 2}, headers=auth(user_id)
    )
    assert spoofed.status_code == 422
    with Session(engine) as session:
        assert len(session.exec(select(Loan)).all()) == 5


@pytest.mark.parametrize("user_id,expected", [(1, [1]), (2, [2]), (3, [1, 2, 3, 4]), (4, [1, 2, 3, 4])])
def test_list_is_scoped_with_and_without_status(loan_context, user_id, expected):
    client, _ = loan_context
    for query in ("", "?status=waiting_rev"):
        response = client.get(f"/loans{query}", headers=auth(user_id))
        assert response.status_code == 200
        assert sorted(row["id"] for row in response.json()) == expected


def test_student_cannot_read_another_users_loan(loan_context):
    client, _ = loan_context
    assert client.get("/loans/1", headers=auth(1)).status_code == 200
    for loan_id in (2, 3, 4, 999):
        assert client.get(f"/loans/{loan_id}", headers=auth(1)).status_code == 404


@pytest.mark.parametrize("user_id", [3, 4])
def test_operators_can_read_all_loans(loan_context, user_id):
    client, _ = loan_context
    for loan_id in range(1, 5):
        assert client.get(f"/loans/{loan_id}", headers=auth(user_id)).status_code == 200


ACTIONS = [
    ("allow", {"type": "accepted", "reason": None}),
    ("deny", {"type": "denied", "reason": "Unavailable"}),
    ("pickup", {"type": "picked_up"}),
    ("close", {"type": "returned"}),
]


@pytest.mark.parametrize("action,body", ACTIONS)
def test_student_cannot_operate_own_or_others_loans(loan_context, action, body):
    client, engine = loan_context
    for loan_id in (1, 2):
        response = client.patch(f"/loans/{action}/{loan_id}", json=body, headers=auth(1))
        assert response.status_code == 403
    with Session(engine) as session:
        for loan in session.exec(select(Loan)).all():
            assert loan.reviewed_by is None
            assert loan.picked_at is None
            assert loan.returned_at is None


@pytest.mark.parametrize("user_id", [3, 4])
@pytest.mark.parametrize("action,body", ACTIONS)
def test_operators_can_operate_own_and_others_loans(loan_context, user_id, action, body):
    client, engine = loan_context
    for loan_id in (1, user_id):
        if action in ("pickup", "close"):
            assert client.patch(f"/loans/allow/{loan_id}", headers=auth(user_id)).status_code == 200
        if action == "close":
            assert client.patch(f"/loans/pickup/{loan_id}", headers=auth(user_id)).status_code == 200
        response = client.patch(
            f"/loans/{action}/{loan_id}", json=body, headers=auth(user_id)
        )
        assert response.status_code == 200
        with Session(engine) as session:
            loan = session.get(Loan, loan_id)
            if action in ("allow", "deny"):
                assert loan.reviewed_by == user_id
            elif action == "pickup":
                assert loan.picked_at is not None
            else:
                assert loan.returned_at is not None
    assert client.patch(
        f"/loans/{action}/999", json=body, headers=auth(user_id)
    ).status_code == 404


def test_all_loan_routes_require_authentication(loan_context):
    client, _ = loan_context
    responses = [
        client.get("/loans"), client.get("/loans/1"),
        client.post("/loans", json=loan_body()),
        *[client.patch(f"/loans/{action}/1", json=body) for action, body in ACTIONS],
    ]
    for response in responses:
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_service_enforces_permissions_without_http_layer(loan_context):
    _, engine = loan_context
    with Session(engine) as session:
        service = LoanService(LoanRepository(session), EquipmentRepository(session))
        student = session.get(User, 1)
        with pytest.raises(LoanPermissionDeniedError):
            service.evaluate(1, LoanEvaluate(type=LoanEvaluateType.ACCEPTED, reason=None), student)
        with pytest.raises(LoanPermissionDeniedError):
            service.record(1, LoanEvent(type=LoanEventType.PICKED_UP), student)


@pytest.mark.parametrize("action,body", [
    ("allow", {"type": "denied", "reason": "No"}),
    ("deny", {"type": "accepted", "reason": None}),
    ("pickup", {"type": "returned"}),
    ("close", {"type": "picked_up"}),
    ("deny", {"reason": None}),
    ("deny", {"reason": "   "}),
])
def test_action_mismatch_and_invalid_denial_are_rejected(loan_context, action, body):
    client, _ = loan_context
    assert client.patch(f"/loans/{action}/1", json=body, headers=auth(3)).status_code == 422


def test_loan_transitions_and_reapproval(loan_context):
    client, _ = loan_context
    headers = auth(3)
    assert client.patch("/loans/pickup/1", headers=headers).status_code == 409
    assert client.patch("/loans/close/1", headers=headers).status_code == 409
    denied = client.patch("/loans/deny/1", json={"reason": "Not available"}, headers=headers)
    assert denied.json()["status"] == "denied"
    assert client.patch("/loans/pickup/1", headers=headers).status_code == 409
    approved = client.patch("/loans/allow/1", headers=headers)
    assert approved.json()["status"] == "waiting_pickup"
    assert approved.json()["reason"] is None
    picked = client.patch("/loans/pickup/1", headers=headers)
    assert picked.status_code == 200
    assert client.patch("/loans/pickup/1", headers=headers).status_code == 409
    assert client.get("/loans/1", headers=headers).json()["picked_at"] == picked.json()["picked_at"]
    assert client.patch("/loans/allow/1", headers=headers).status_code == 409
    returned = client.patch("/loans/close/1", headers=headers)
    assert returned.json()["status"] == "returned"
    assert client.patch("/loans/close/1", headers=headers).status_code == 409
    assert client.patch("/loans/deny/1", json={"reason": "No"}, headers=headers).status_code == 409


@pytest.mark.parametrize("ids", [[999], [1, 999], [1]])
def test_missing_or_inactive_equipment_aborts_creation(loan_context, ids):
    client, engine = loan_context
    if ids == [1]:
        with Session(engine) as session:
            equipment = session.get(Equipment, 1)
            equipment.active = False
            session.add(equipment)
            session.commit()
    response = client.post("/loans", json=loan_body() | {"equipments": ids}, headers=auth(1))
    assert response.status_code == 409
    with Session(engine) as session:
        assert len(session.exec(select(Loan)).all()) == 4


def test_mixed_timezones_are_normalized_and_return_equipment(loan_context):
    client, engine = loan_context
    body = loan_body() | {
        "pickup_date": "2030-01-01T09:00:00-03:00",
        "due_date": "2030-01-01T13:00:00",
    }
    response = client.post("/loans", json=body, headers=auth(1))
    assert response.status_code == 201
    assert response.json()["pickup_date"] == "2030-01-01T12:00:00Z"
    assert response.json()["due_date"] == "2030-01-01T13:00:00Z"
    assert response.json()["equipments"][0]["active"] is True
    with Session(engine) as session:
        stored = session.get(Loan, response.json()["id"])
        assert stored.pickup_date == datetime(2030, 1, 1, 12)
    body["due_date"] = "2030-01-01T11:00:00Z"
    assert client.post("/loans", json=body, headers=auth(1)).status_code == 422


def test_late_filter_and_response_use_utc(loan_context):
    client, engine = loan_context
    with Session(engine) as session:
        loan = session.get(Loan, 1)
        loan.reviewed_by = 3
        loan.picked_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        loan.due_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        session.add(loan)
        session.commit()
    response = client.get("/loans?status=late", headers=auth(1))
    assert response.status_code == 200
    assert [(row["id"], row["status"]) for row in response.json()] == [(1, "late")]


@pytest.mark.parametrize("user_id,expected", [(None, 401), (1, 403), (3, 403), (4, 204)])
def test_user_administration_requires_admin(loan_context, user_id, expected):
    client, _ = loan_context
    headers = auth(user_id) if user_id else {}
    for operation in ("deactivate", "activate"):
        response = client.patch(f"/users/{operation}/2", headers=headers)
        assert response.status_code == expected
        if expected == 204:
            assert response.content == b""
    response = client.get("/users", headers=headers)
    assert response.status_code == (200 if expected == 204 else expected)


def test_nonexistent_user_returns_404(loan_context):
    client, _ = loan_context
    assert client.patch("/users/activate/999", headers=auth(4)).status_code == 404


@pytest.mark.parametrize("user_id,expected", [(None, 401), (1, 403), (3, 201), (4, 201)])
def test_inventory_mutations_require_operator(loan_context, user_id, expected):
    client, _ = loan_context
    headers = auth(user_id) if user_id else {}
    response = client.post("/equipments/categories", json={"name": "New", "description": "New"}, headers=headers)
    assert response.status_code == expected
    response = client.post("/equipments", json={"name": "New", "code": "NEW", "category_id": 1}, headers=headers)
    assert response.status_code == expected
    response = client.delete("/equipments/1", headers=headers)
    assert response.status_code == (204 if expected == 201 else expected)
    if expected == 201:
        response = client.delete("/equipments/categories/2", headers=headers)
        assert response.status_code == 204
        assert response.content == b""
    else:
        assert client.delete("/equipments/categories/1", headers=headers).status_code == expected


def test_inventory_queries_and_constraint_errors(loan_context):
    client, _ = loan_context
    assert client.get("/equipments").status_code == 401
    assert client.get("/equipments/categories").status_code == 401
    assert client.get("/equipments/categories", headers=auth(1)).status_code == 200
    missing = client.post("/equipments", json={"name": "New", "code": "NEW", "category_id": 999}, headers=auth(3))
    assert missing.status_code == 404
    duplicate = client.post("/equipments", json={"name": "New", "code": "NB-1", "category_id": 1}, headers=auth(3))
    assert duplicate.status_code == 409
    assert client.delete("/equipments/categories/1", headers=auth(3)).status_code == 409
    assert client.delete("/equipments/1", headers=auth(3)).status_code == 204
    assert client.get("/equipments?active=true", headers=auth(1)).json() == []
    inactive = client.get("/equipments?active=false", headers=auth(1)).json()
    assert inactive[0]["active"] is False


def test_signup_duplicate_and_internal_errors_are_safe(loan_context):
    from unittest.mock import MagicMock

    from src.core.dependencies import get_user_serv
    from src.services.users import UserService

    client, _ = loan_context
    body = {"name": "Test User", "email": "new@example.com", "phone": "11888888888", "password": "secret123"}
    assert client.post("/users", json=body).status_code == 201
    duplicate = client.post("/users", json=body)
    assert duplicate.status_code == 409
    assert "SQL" not in duplicate.text

    service = MagicMock(spec=UserService)
    service.create.side_effect = RuntimeError("sensitive database details")
    app.dependency_overrides[get_user_serv] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as safe_client:
            response = safe_client.post("/users", json=body)
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
    finally:
        app.dependency_overrides.pop(get_user_serv, None)
