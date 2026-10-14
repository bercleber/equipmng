import pytest
from pydantic import ValidationError

from src.core.settings import Settings


def test_cors_requires_explicit_origins():
    values = dict(
        db_driver="mysql+pymysql", db_host="localhost", db_port=3306,
        db_user="test", db_pass="test", db_name="test",
        jwt_secret="configuration-test-key-at-least-32-bytes",
        jwt_algorithm="HS256", jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values, cors_origins=["*"])
    configured = Settings(
        _env_file=None, **values, cors_origins=["https://app.example.com"]
    )
    assert configured.cors_origins == ["https://app.example.com"]


@pytest.mark.parametrize("days", [1, 7, 30])
def test_refresh_lifetime_reads_environment(monkeypatch, days):
    monkeypatch.setenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", str(days))
    assert Settings(_env_file=None).jwt_refresh_token_expire_days == days


@pytest.mark.parametrize("days", ["0", "-1", "invalid", "1.5"])
def test_refresh_lifetime_rejects_invalid_values(monkeypatch, days):
    monkeypatch.setenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", days)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_refresh_lifetime_requires_configuration(monkeypatch):
    monkeypatch.delenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
