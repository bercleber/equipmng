from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt
import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from src.core.settings import get_settings
from src.main import app
from src.models.models import Loan, RefreshSession, RefreshToken, User
from src.services import auth as auth_service


def digest(token):
    return sha256(token.encode()).hexdigest()


@pytest.fixture
def refresh_context(api_context, monkeypatch):
    client, engine = api_context
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setattr(auth_service, "utc_now", lambda: now)
    with Session(engine) as session:
        session.get(User, 1).pass_hash = PasswordHash.recommended().hash("secret123")
        session.commit()
    response = client.post(
        "/auth/login", json={"email": "user1@example.com", "password": "secret123"}
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    return client, engine, response.json(), now


def refresh(client, token):
    return client.post("/auth/refresh", json={"refresh_token": token})


def assert_unauthorized(response):
    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid or expired refresh token"}


def test_login_persists_only_hash_and_expires_in_seven_days(refresh_context):
    _, engine, tokens, now = refresh_context
    expires = datetime.fromisoformat(tokens["refresh_expires_at"])
    assert expires - now == timedelta(days=7)
    assert len(tokens["refresh_token"]) == 43
    with Session(engine) as session:
        stored = session.exec(select(RefreshToken)).one()
        family = session.exec(select(RefreshSession)).one()
        assert stored.token_hash == digest(tokens["refresh_token"])
        assert stored.used_at is None
        assert stored.session_id == family.id
        assert family.user_id == 1
        assert family.revoked_at is None
        assert family.expires_at - family.created_at == timedelta(days=7)
        assert family.created_at == now.replace(tzinfo=None)
        assert tokens["refresh_token"] not in repr(stored.model_dump())
        assert tokens["access_token"] not in repr(stored.model_dump())


@pytest.mark.parametrize("days", [1, 14])
def test_configured_lifetime_applies_only_to_new_sessions(refresh_context, monkeypatch, days):
    client, engine, initial, now = refresh_context
    settings = app.dependency_overrides[get_settings]().model_copy(
        update={"jwt_refresh_token_expire_days": days}
    )
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)
    logged_in = client.post(
        "/auth/login", json={"email": "user1@example.com", "password": "secret123"}
    )
    assert logged_in.status_code == 200
    tokens = logged_in.json()
    assert datetime.fromisoformat(tokens["refresh_expires_at"]) - now == timedelta(days=days)
    with Session(engine) as session:
        token = session.get(RefreshToken, digest(tokens["refresh_token"]))
        family = session.get(RefreshSession, token.session_id)
        assert family.expires_at - family.created_at == timedelta(days=days)

    # Configuration changes must not extend or shorten existing sessions.
    rotated = refresh(client, initial["refresh_token"])
    assert rotated.status_code == 200
    assert rotated.json()["refresh_expires_at"] == initial["refresh_expires_at"]


def test_refresh_rotates_and_preserves_absolute_expiration(refresh_context, monkeypatch):
    client, engine, initial, now = refresh_context
    monkeypatch.setattr(auth_service, "utc_now", lambda: now + timedelta(days=1))
    response = refresh(client, initial["refresh_token"])
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    current = response.json()
    assert current["refresh_token"] != initial["refresh_token"]
    assert current["access_token"] != initial["access_token"]
    assert current["refresh_expires_at"] == initial["refresh_expires_at"]
    assert current["token_type"] == "bearer"
    with Session(engine) as session:
        previous = session.get(RefreshToken, digest(initial["refresh_token"]))
        replacement = session.get(RefreshToken, digest(current["refresh_token"]))
        assert previous.used_at == (now + timedelta(days=1)).replace(tzinfo=None)
        assert replacement.used_at is None
        assert previous.session_id == replacement.session_id
        assert len(session.exec(select(RefreshSession)).all()) == 1


def test_refreshed_access_token_authenticates_and_keeps_short_lifetime(refresh_context):
    client, _, initial, _ = refresh_context
    response = refresh(client, initial["refresh_token"])
    assert response.status_code == 200
    current = response.json()
    # A fresh jti makes successive access tokens distinct even in the same second.
    assert current["access_token"] != initial["access_token"]
    claims = jwt.decode(current["access_token"], options={"verify_signature": False})
    assert claims["type"] == "access"
    assert claims["sub"] == "1"
    assert claims["exp"] - claims["iat"] == get_settings().jwt_access_token_expire_minutes * 60
    authorized = client.get("/loans", headers={"Authorization": f"Bearer {current['access_token']}"})
    assert authorized.status_code == 200
    assert [loan["id"] for loan in authorized.json()] == [1]


def test_replay_revokes_all_descendants_but_not_other_logins(refresh_context):
    client, engine, initial, _ = refresh_context
    second_login = client.post(
        "/auth/login", json={"email": "user1@example.com", "password": "secret123"}
    ).json()
    second = refresh(client, initial["refresh_token"]).json()
    third = refresh(client, second["refresh_token"]).json()
    assert_unauthorized(refresh(client, initial["refresh_token"]))
    assert_unauthorized(refresh(client, third["refresh_token"]))
    assert_unauthorized(refresh(client, second["refresh_token"]))
    assert refresh(client, second_login["refresh_token"]).status_code == 200
    with Session(engine) as session:
        token = session.get(RefreshToken, digest(initial["refresh_token"]))
        assert session.get(RefreshSession, token.session_id).revoked_at is not None


@pytest.mark.parametrize("offset,expected", [
    (timedelta(days=7) - timedelta(microseconds=1), 200),
    (timedelta(days=7), 401),
    (timedelta(days=8), 401),
])
def test_expiry_boundary(refresh_context, monkeypatch, offset, expected):
    client, _, initial, now = refresh_context
    monkeypatch.setattr(auth_service, "utc_now", lambda: now + offset)
    response = refresh(client, initial["refresh_token"])
    assert response.status_code == expected
    if expected == 401:
        assert_unauthorized(response)


@pytest.mark.parametrize("kind", ["unknown", "tampered", "access"])
def test_invalid_tokens_cannot_refresh_or_revoke_valid_session(refresh_context, kind):
    client, engine, initial, _ = refresh_context
    tokens = {
        "unknown": "unknown-token",
        "tampered": initial["refresh_token"] + "x",
        "access": initial["access_token"],
    }
    assert_unauthorized(refresh(client, tokens[kind]))
    with Session(engine) as session:
        assert session.exec(select(RefreshSession)).one().revoked_at is None
        assert session.exec(select(RefreshToken)).one().used_at is None
    assert refresh(client, initial["refresh_token"]).status_code == 200


@pytest.mark.parametrize("body", [None, {}, {"refresh_token": None}, {"refresh_token": ""}, {"refresh_token": "x" * 257}])
def test_missing_or_invalid_refresh_body(api_context, body):
    client, engine = api_context
    response = client.post("/auth/refresh", json=body)
    assert response.status_code == 422
    with Session(engine) as session:
        assert session.exec(select(RefreshToken)).all() == []


def test_refresh_token_cannot_authenticate_as_access_token(refresh_context):
    client, _, initial, _ = refresh_context
    response = client.get("/loans", headers={"Authorization": f"Bearer {initial['refresh_token']}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_refresh_does_not_require_valid_access_token(refresh_context, auth_headers):
    client, _, initial, _ = refresh_context
    response = client.post(
        "/auth/refresh", json={"refresh_token": initial["refresh_token"]},
        headers=auth_headers(1, expired=True),
    )
    assert response.status_code == 200


def test_inactive_user_cannot_refresh_and_session_stays_revoked(refresh_context):
    client, engine, initial, _ = refresh_context
    with Session(engine) as session:
        session.get(User, 1).active = False
        session.commit()
    response = refresh(client, initial["refresh_token"])
    assert response.status_code == 403
    assert response.json() == {"detail": "User is inactive"}
    with Session(engine) as session:
        assert session.exec(select(RefreshSession)).one().revoked_at is not None
        session.get(User, 1).active = True
        session.commit()
    assert_unauthorized(refresh(client, initial["refresh_token"]))


def test_deleted_user_cascades_refresh_records(refresh_context):
    client, engine, initial, _ = refresh_context
    with Session(engine) as session:
        session.exec(delete(Loan).where(Loan.requested_by == 1))
        session.exec(delete(User).where(User.id == 1))
        session.commit()
        assert session.exec(select(RefreshSession)).all() == []
        assert session.exec(select(RefreshToken)).all() == []
    assert_unauthorized(refresh(client, initial["refresh_token"]))


def test_current_role_is_used_after_refresh(refresh_context):
    client, engine, initial, _ = refresh_context
    with Session(engine) as session:
        session.get(User, 1).role_id = 1
        session.commit()
    response = refresh(client, initial["refresh_token"])
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/users", headers=headers).status_code == 200


def test_failed_rotation_rolls_back_consumption(refresh_context, monkeypatch):
    client, engine, initial, _ = refresh_context

    def fail_commit(self):
        raise SQLAlchemyError("sensitive database details")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        with TestClient(app, raise_server_exceptions=False) as safe_client:
            response = refresh(safe_client, initial["refresh_token"])
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
    with Session(engine) as session:
        assert session.exec(select(RefreshToken)).one().used_at is None
        assert session.exec(select(RefreshSession)).one().revoked_at is None
    assert refresh(client, initial["refresh_token"]).status_code == 200


def test_failed_login_persistence_does_not_leave_partial_session(refresh_context, monkeypatch):
    _, engine, _, _ = refresh_context

    def fail_commit(self):
        raise SQLAlchemyError("sensitive database details")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/auth/login", json={"email": "user1@example.com", "password": "secret123"}
            )
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
    with Session(engine) as session:
        # Only the successful login from the fixture remains.
        assert len(session.exec(select(RefreshSession)).all()) == 1
        assert len(session.exec(select(RefreshToken)).all()) == 1
