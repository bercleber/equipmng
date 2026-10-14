"""HTTP contracts exercised through the real service and repository layers."""

from datetime import datetime, timedelta, timezone

import pytest
from pwdlib import PasswordHash
from sqlmodel import Session, select

from src.main import app
from src.models.models import Category, Equipment, Loan, LoanEquipmentLink, LoanStatus, User


SIGNUP = {
    "name": "New Student",
    "email": "new@example.com",
    "phone": "11888888888",
    "password": "secret123",
}
LOAN = {
    "pickup_date": "2030-01-01T12:00:00Z",
    "due_date": "2030-01-02T12:00:00Z",
    "equipments": [1],
}

# Keep this inventory explicit so adding a route also requires updating tests.
# Entries contain the OpenAPI path, an actual request path, and valid input.
PROTECTED_ROUTES = [
    ("GET", "/users", "/users", None),
    ("PATCH", "/users/activate/{user_id}", "/users/activate/2", None),
    ("PATCH", "/users/deactivate/{user_id}", "/users/deactivate/2", None),
    ("GET", "/equipments", "/equipments", None),
    ("POST", "/equipments", "/equipments", {"name": "Camera", "code": "CAM-1", "category_id": 1}),
    ("DELETE", "/equipments/{id}", "/equipments/1", None),
    ("GET", "/equipments/categories", "/equipments/categories", None),
    ("POST", "/equipments/categories", "/equipments/categories", {"name": "Cameras", "description": "Cameras"}),
    ("DELETE", "/equipments/categories/{id}", "/equipments/categories/1", None),
    ("GET", "/loans", "/loans", None),
    ("POST", "/loans", "/loans", LOAN),
    ("GET", "/loans/{loan_id}", "/loans/1", None),
    ("PATCH", "/loans/allow/{loan_id}", "/loans/allow/1", {}),
    ("PATCH", "/loans/deny/{loan_id}", "/loans/deny/1", {"reason": "Unavailable"}),
    ("PATCH", "/loans/pickup/{loan_id}", "/loans/pickup/1", {}),
    ("PATCH", "/loans/close/{loan_id}", "/loans/close/1", {}),
]


def test_route_inventory_matches_registered_api():
    registered = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "patch", "put", "delete"}
    }
    expected = {(method, path) for method, path, _, _ in PROTECTED_ROUTES}
    expected.update({("POST", "/users"), ("POST", "/auth/login"), ("POST", "/auth/refresh")})
    assert registered == expected


@pytest.mark.parametrize("method,template,path,body", PROTECTED_ROUTES)
@pytest.mark.parametrize("identity", ["missing", "invalid", "expired", "inactive", "deleted"])
def test_every_protected_route_checks_identity(
    api_context, auth_headers, method, template, path, body, identity
):
    client, engine = api_context
    headers = {}
    expected = 401
    if identity == "invalid":
        headers = {"Authorization": "Bearer invalid-token"}
    elif identity == "expired":
        headers = auth_headers(4, expired=True)
    elif identity == "deleted":
        headers = auth_headers(999)
    elif identity == "inactive":
        with Session(engine) as session:
            user = session.get(User, 4)
            user.active = False
            session.commit()
        headers = auth_headers(4)
        expected = 403

    response = client.request(method, path, json=body, headers=headers)

    assert response.status_code == expected, response.text
    if expected == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    with Session(engine) as session:
        assert len(session.exec(select(User)).all()) == 4
        assert session.get(User, 2).active is True
        assert len(session.exec(select(Category)).all()) == 1
        assert len(session.exec(select(Equipment)).all()) == 1
        assert session.get(Equipment, 1).active is True
        loans = session.exec(select(Loan)).all()
        assert len(loans) == 4
        assert all(
            loan.reviewed_by is None and loan.picked_at is None and loan.returned_at is None
            for loan in loans
        )


def test_signup_activation_login_and_token_revocation(api_context, auth_headers):
    client, engine = api_context
    created = client.post("/users", json=SIGNUP)
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["active"] is False
    assert user["role"]["name"] == "aluno"
    assert "password" not in user and "pass_hash" not in user
    with Session(engine) as session:
        stored = session.get(User, user["id"])
        assert stored.pass_hash != SIGNUP["password"]
        assert PasswordHash.recommended().verify(SIGNUP["password"], stored.pass_hash)

    credentials = {key: SIGNUP[key] for key in ("email", "password")}
    assert client.post("/auth/login", json=credentials).status_code == 403
    activated = client.patch(f"/users/activate/{user['id']}", headers=auth_headers(4))
    assert activated.status_code == 204 and activated.content == b""
    logged_in = client.post("/auth/login", json=credentials)
    assert logged_in.status_code == 200, logged_in.text
    assert logged_in.json()["token_type"] == "bearer"
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    assert client.get("/loans", headers=headers).json() == []
    loan = client.post("/loans", json=LOAN, headers=headers)
    assert loan.status_code == 201, loan.text
    assert loan.json()["requested_by"] == user["id"]
    assert client.get(f"/loans/{loan.json()['id']}", headers=headers).status_code == 200
    assert client.get("/users", headers=headers).status_code == 403
    deactivated = client.patch(f"/users/deactivate/{user['id']}", headers=auth_headers(4))
    assert deactivated.status_code == 204 and deactivated.content == b""
    assert client.get("/loans", headers=headers).status_code == 403
    assert client.post("/auth/login", json=credentials).status_code == 403


@pytest.mark.parametrize("field,value", [("email", "user1@example.com"), ("phone", "11999999991")])
def test_signup_rejects_each_unique_field(api_context, field, value):
    client, engine = api_context
    response = client.post("/users", json=SIGNUP | {field: value})
    assert response.status_code == 409, response.text
    with Session(engine) as session:
        assert len(session.exec(select(User)).all()) == 4


@pytest.mark.parametrize("active,expected", [(None, [1, 2, 3, 4]), ("true", [1, 3, 4]), ("false", [2])])
def test_users_filter_and_safe_response(api_context, auth_headers, active, expected):
    client, engine = api_context
    with Session(engine) as session:
        session.get(User, 2).active = False
        session.commit()
    response = client.get("/users", params={} if active is None else {"active": active}, headers=auth_headers(4))
    assert response.status_code == 200
    assert sorted(user["id"] for user in response.json()) == expected
    for user in response.json():
        assert set(user) == {"id", "name", "email", "phone", "active", "role"}
        assert set(user["role"]) == {"id", "name"}


@pytest.mark.parametrize("path", [
    "/users/activate/999", "/users/deactivate/999",
])
def test_missing_user_on_status_change(api_context, auth_headers, path):
    client, _ = api_context
    assert client.patch(path, headers=auth_headers(4)).status_code == 404


def test_category_crud_and_duplicate_constraint(api_context, auth_headers):
    client, engine = api_context
    headers = auth_headers(3)
    body = {"name": "Cameras", "description": "Photo and video equipment"}
    created = client.post("/equipments/categories", json=body, headers=headers)
    assert created.status_code == 201, created.text
    category_id = created.json()["id"]
    assert created.json() == body | {"id": category_id}
    duplicate = client.post("/equipments/categories", json=body, headers=headers)
    assert duplicate.status_code == 409, duplicate.text
    listed = client.get("/equipments/categories", headers=auth_headers(1))
    assert listed.status_code == 200
    assert created.json() in listed.json()
    deleted = client.delete(f"/equipments/categories/{category_id}", headers=headers)
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.delete(f"/equipments/categories/{category_id}", headers=headers).status_code == 404
    with Session(engine) as session:
        assert session.get(Category, category_id) is None
        assert session.get(Category, 1) is not None


@pytest.mark.parametrize("user_id", [1, 3, 4])
def test_inventory_reads_and_soft_delete(api_context, auth_headers, user_id):
    client, engine = api_context
    body = {"name": "Camera", "code": "CAM-1", "category_id": 1}
    created = client.post("/equipments", json=body, headers=auth_headers(3))
    assert created.status_code == 201, created.text
    equipment_id = created.json()["id"]
    assert created.json() == {
        "id": equipment_id, "name": "Camera", "code": "CAM-1", "active": True,
        "category": {"id": 1, "name": "Computers"},
    }
    deleted = client.delete(f"/equipments/{equipment_id}", headers=auth_headers(3))
    assert deleted.status_code == 204 and deleted.content == b""
    for params, expected in [({}, [1, equipment_id]), ({"active": "true"}, [1]), ({"active": "false"}, [equipment_id])]:
        listed = client.get("/equipments", params=params, headers=auth_headers(user_id))
        assert listed.status_code == 200
        assert sorted(row["id"] for row in listed.json()) == expected
    with Session(engine) as session:
        assert session.get(Equipment, equipment_id).active is False
    # Soft deletion does not release the code or the category's foreign key.
    assert client.post("/equipments", json=body, headers=auth_headers(3)).status_code == 409
    assert client.delete("/equipments/categories/1", headers=auth_headers(3)).status_code == 409


@pytest.mark.parametrize("path", ["/equipments/999", "/equipments/categories/999"])
def test_missing_inventory_delete(api_context, auth_headers, path):
    client, _ = api_context
    assert client.delete(path, headers=auth_headers(3)).status_code == 404


@pytest.mark.parametrize("status", list(LoanStatus))
@pytest.mark.parametrize("user_id", [1, 3, 4])
def test_every_loan_status_filter_respects_ownership(api_context, auth_headers, status, user_id):
    client, engine = api_context
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    # Large margins avoid clock/timezone boundary sensitivity.
    expected = []
    with Session(engine) as session:
        for owner in (1, 2):
            for state in LoanStatus:
                loan = Loan(
                    requested_by=owner, pickup_date=now - timedelta(days=3),
                    due_date=now + timedelta(days=3),
                )
                if state != LoanStatus.WAITING_REVISION:
                    loan.reviewed_by = 3
                if state == LoanStatus.DENIED:
                    loan.reason = "Unavailable"
                if state in (LoanStatus.ON_LOAN, LoanStatus.LATE, LoanStatus.RETURNED):
                    loan.picked_at = now - timedelta(days=2)
                if state in (LoanStatus.LATE, LoanStatus.RETURNED):
                    loan.due_date = now - timedelta(days=1)
                if state == LoanStatus.RETURNED:
                    loan.returned_at = now
                session.add(loan)
                session.flush()
                if state == status and (user_id != 1 or owner == 1):
                    expected.append(loan.id)
        if status == LoanStatus.WAITING_REVISION:
            expected.extend([1] if user_id == 1 else [1, 2, 3, 4])
        session.commit()
    response = client.get("/loans", params={"status": status.value}, headers=auth_headers(user_id))
    assert response.status_code == 200, response.text
    assert sorted(row["id"] for row in response.json()) == sorted(expected)
    assert all(row["status"] == status.value for row in response.json())


def test_duplicate_equipment_ids_create_one_link(api_context, auth_headers):
    client, engine = api_context
    created = client.post("/loans", json=LOAN | {"equipments": [1, 1]}, headers=auth_headers(1))
    assert created.status_code == 201, created.text
    assert [row["id"] for row in created.json()["equipments"]] == [1]
    with Session(engine) as session:
        links = session.exec(select(LoanEquipmentLink).where(LoanEquipmentLink.loan_id == created.json()["id"])).all()
        assert len(links) == 1


INVALID_REQUESTS = [
    ("POST", "/auth/login", {}),
    ("POST", "/auth/login", {"email": "invalid", "password": "secret123"}),
    ("POST", "/users", {}),
    ("POST", "/users", SIGNUP | {"name": "Short"}),
    ("POST", "/users", SIGNUP | {"phone": "123"}),
    ("POST", "/users", SIGNUP | {"password": "123"}),
    ("GET", "/users?active=invalid", None),
    ("PATCH", "/users/activate/not-an-id", None),
    ("PATCH", "/users/deactivate/not-an-id", None),
    ("GET", "/equipments?active=invalid", None),
    ("POST", "/equipments", {}),
    ("POST", "/equipments", {"name": "Camera", "code": "C" * 51, "category_id": 1}),
    ("POST", "/equipments", {"name": "Camera", "code": "CAM", "category_id": 0}),
    ("POST", "/equipments/categories", {}),
    ("POST", "/equipments/categories", {"name": "N" * 31, "description": "D"}),
    ("POST", "/equipments/categories", {"name": "N", "description": "D" * 301}),
    ("DELETE", "/equipments/not-an-id", None),
    ("DELETE", "/equipments/categories/not-an-id", None),
    ("GET", "/loans?status=invalid", None),
    ("GET", "/loans/not-an-id", None),
    ("POST", "/loans", {}),
    ("POST", "/loans", LOAN | {"equipments": []}),
    ("POST", "/loans", LOAN | {"equipments": [0]}),
    ("POST", "/loans", LOAN | {"equipments": [-1]}),
    ("POST", "/loans", LOAN | {"equipments": ["invalid"]}),
    ("POST", "/loans", LOAN | {"pickup_date": "invalid"}),
    ("POST", "/loans", LOAN | {"due_date": LOAN["pickup_date"]}),
    ("POST", "/loans", LOAN | {"due_date": "2029-12-31T12:00:00Z"}),
    ("PATCH", "/loans/allow/1", {"reason": "Cannot approve with a reason"}),
    ("PATCH", "/loans/deny/1", {}),
    ("PATCH", "/loans/deny/1", None),
    ("PATCH", "/loans/pickup/1", {"unexpected": True}),
    ("PATCH", "/loans/close/1", {"unexpected": True}),
    *[("PATCH", f"/loans/{action}/not-an-id", {"reason": "No"} if action == "deny" else {})
      for action in ("allow", "deny", "pickup", "close")],
]


@pytest.mark.parametrize("method,path,body", INVALID_REQUESTS)
def test_validation_errors_do_not_mutate_database(api_context, auth_headers, method, path, body):
    client, engine = api_context
    response = client.request(method, path, json=body, headers=auth_headers(4))
    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], list)
    with Session(engine) as session:
        assert len(session.exec(select(User)).all()) == 4
        assert len(session.exec(select(Category)).all()) == 1
        assert len(session.exec(select(Equipment)).all()) == 1
        loans = session.exec(select(Loan)).all()
        assert len(loans) == 4
        assert all(loan.reviewed_by is None and loan.picked_at is None and loan.returned_at is None for loan in loans)
