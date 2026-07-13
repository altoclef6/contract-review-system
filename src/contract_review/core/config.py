from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "企业级多源合同智能审查系统 API"
    environment: Literal["local", "dev", "test", "prod"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    log_level: str = "INFO"
    frontend_url: str = "http://127.0.0.1:5173"

    upload_dir: Path = Path("data/uploads")
    report_dir: Path = Path("data/reports")
    contract_data_dir: Path = Path("data/contracts")
    model_config_data_dir: Path = Path("data/model-configs")
    prompt_template_data_dir: Path = Path("data/prompt-templates")
    chat_data_dir: Path = Path("data/chats")
    workflow_data_dir: Path = Path("data/workflows")
    notification_data_dir: Path = Path("data/notifications")
    security_data_dir: Path = Path("data/security")
    max_upload_size_mb: int = 50

    jwt_secret_key: SecretStr
    jwt_access_token_minutes: int = 30
    jwt_refresh_token_days: int = 7
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: SecretStr
    bootstrap_admin_name: str = "System Admin"
    model_credential_encryption_key: SecretStr | None = None
    postgres_password: SecretStr | None = None

    llm_provider: Literal["openai", "openai_compatible", "deepseek"] = "openai_compatible"
    llm_model_name: str = "gpt-4.1-mini"
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 60
    enable_llm: bool = True

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://contract_review:contract_review@localhost:5432/contract_review"
    )
    database_enabled: bool = False
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    redis_enabled: bool = False
    cache_ttl_seconds: int = 300
    rate_limit_per_minute: int = 120
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    celery_broker_url: SecretStr = SecretStr("redis://localhost:6379/1")
    celery_result_backend: SecretStr = SecretStr("redis://localhost:6379/2")

    tesseract_cmd: str | None = None
    libreoffice_cmd: str | None = None
    tessdata_dir: Path | None = None
    ocr_languages: str = "chi_sim+eng"

    @model_validator(mode="after")
    def validate_deployment_security(self) -> Settings:
        if self.environment != "prod":
            return self
        required = {
            "JWT_SECRET_KEY": self.jwt_secret_key.get_secret_value(),
            "BOOTSTRAP_ADMIN_PASSWORD": self.bootstrap_admin_password.get_secret_value(),
            "DATABASE_URL": self.database_url.get_secret_value(),
            "POSTGRES_PASSWORD": (
                self.postgres_password.get_secret_value() if self.postgres_password else ""
            ),
            "MODEL_CREDENTIAL_ENCRYPTION_KEY": (
                self.model_credential_encryption_key.get_secret_value()
                if self.model_credential_encryption_key
                else ""
            ),
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"Production configuration is missing: {', '.join(missing)}")
        if len(required["JWT_SECRET_KEY"]) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters in production")
        if len(required["BOOTSTRAP_ADMIN_PASSWORD"]) < 12:
            raise ValueError("BOOTSTRAP_ADMIN_PASSWORD is too weak for production")
        forbidden = {"change-me-in-production", "admin12345!", "contract_review"}
        if required["JWT_SECRET_KEY"].lower() in forbidden:
            raise ValueError("JWT_SECRET_KEY uses a forbidden production default")
        if required["BOOTSTRAP_ADMIN_PASSWORD"].lower() in forbidden:
            raise ValueError("BOOTSTRAP_ADMIN_PASSWORD uses a forbidden production default")
        if "contract_review:contract_review@" in required["DATABASE_URL"].lower():
            raise ValueError("DATABASE_URL uses a forbidden production password")
        if self.debug:
            raise ValueError("DEBUG must be disabled in production")
        return self

    @field_validator("allowed_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def resolve_llm_api_key(self) -> SecretStr | None:
        if self.llm_api_key is not None:
            return self.llm_api_key
        if self.llm_provider == "deepseek" and self.deepseek_api_key is not None:
            return self.deepseek_api_key
        if self.openai_api_key is not None:
            return self.openai_api_key
        return self.deepseek_api_key

    def resolve_llm_base_url(self) -> str | None:
        if self.llm_base_url:
            return self.llm_base_url
        if self.llm_provider == "deepseek":
            return "https://api.deepseek.com/v1"
        return None

    def resolve_model_credential_encryption_key(self) -> str:
        if self.model_credential_encryption_key is not None:
            return self.model_credential_encryption_key.get_secret_value()
        if self.environment == "prod":
            raise ValueError("MODEL_CREDENTIAL_ENCRYPTION_KEY is required in production")
        return self.jwt_secret_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values are supplied by BaseSettings
