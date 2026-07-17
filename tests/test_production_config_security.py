import pytest
from pydantic import ValidationError

from contract_review.core.config import Settings
from contract_review.core.security import TokenError, decode_token


def _production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "environment": "prod",
        "debug": False,
        "jwt_secret_key": "j" * 48,
        "bootstrap_admin_password": "Strong-Admin-Password-2026!",
        "database_url": "postgresql+psycopg://app:strong-password@db/contracts",
        "postgres_password": "strong-password",
        "model_credential_encryption_key": "m" * 48,
        "database_enabled": True,
        "redis_enabled": True,
        "review_tasks_sync_fallback": False,
        "allowed_origins": ["https://contracts.example.com"],
        "trusted_hosts": ["contracts.example.com"],
        "_env_file": None,
    }
    values.update(overrides)
    return values


def test_production_requires_model_encryption_key() -> None:
    with pytest.raises(ValidationError, match="MODEL_CREDENTIAL_ENCRYPTION_KEY"):
        Settings(**_production_settings(model_credential_encryption_key=None))


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(**_production_settings(jwt_secret_key="short"))


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(**_production_settings(debug=True))


def test_production_configuration_accepts_strong_values() -> None:
    settings = Settings(**_production_settings())
    assert settings.environment == "prod"
    assert settings.resolve_model_credential_encryption_key() == "m" * 48


def test_malformed_token_has_controlled_error() -> None:
    with pytest.raises(TokenError):
        decode_token("a.b.c", secret="test-secret", expected_type="access")


def test_test_environment_does_not_read_dotenv(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("APP_NAME=must-not-be-read\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        jwt_secret_key="test-secret",
        bootstrap_admin_password="Admin12345!",
    )

    assert settings.app_name != "must-not-be-read"
