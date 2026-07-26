from __future__ import annotations

import os
import secrets
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None if os.environ.get("ENVIRONMENT", "").casefold() == "test" else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "企业级多源合同智能审查系统 API"
    app_mode: Literal["web", "desktop"] = "web"
    environment: Literal["local", "dev", "test", "prod"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    allowed_origins: Annotated[list[str], NoDecode] = Field(
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
    review_task_data_dir: Path = Path("data/review-tasks")
    rule_center_data_dir: Path = Path("data/rule-center")
    knowledge_center_data_dir: Path = Path("data/knowledge-center")
    risk_feedback_data_dir: Path = Path("data/risk-feedback")
    max_upload_size_mb: int = 50
    max_pdf_pages: int = 500
    max_image_pixels: int = 80_000_000
    ocr_timeout_seconds: int = 120

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
    login_max_attempts: int = 5
    login_window_seconds: int = 300
    trust_proxy_headers: bool = False
    trusted_proxy_cidrs: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trusted_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    celery_broker_url: SecretStr = SecretStr("redis://localhost:6379/1")
    celery_result_backend: SecretStr = SecretStr("redis://localhost:6379/2")
    review_tasks_sync_fallback: bool = True
    review_task_timeout_seconds: int = 900
    review_task_max_retries: int = 2
    desktop_startup_token: SecretStr | None = None
    desktop_max_concurrent_tasks: int = Field(default=2, ge=1, le=8)
    desktop_data_dir: Path | None = None

    tesseract_cmd: str | None = None
    libreoffice_cmd: str | None = None
    tessdata_dir: Path | None = None
    ocr_languages: str = "chi_sim+eng"

    @model_validator(mode="after")
    def validate_deployment_security(self) -> Settings:
        if self.app_mode == "desktop":
            if not self.desktop_startup_token:
                raise ValueError("DESKTOP_STARTUP_TOKEN is required in desktop mode")
            startup_token = self.desktop_startup_token.get_secret_value()
            if len(startup_token) < 32 or not secrets.compare_digest(
                startup_token.strip(), startup_token
            ):
                raise ValueError(
                    "DESKTOP_STARTUP_TOKEN must contain at least 32 characters and no whitespace"
                )
            if self.redis_enabled:
                raise ValueError("REDIS_ENABLED must be false in desktop mode")
            data_root = self.desktop_data_dir
            if data_root is None:
                local_app_data = os.environ.get("LOCALAPPDATA")
                if not local_app_data:
                    raise ValueError(
                        "DESKTOP_DATA_DIR or LOCALAPPDATA is required in desktop mode"
                    )
                data_root = Path(local_app_data) / "ContractReview"
            data_root = data_root.expanduser().resolve()
            self.desktop_data_dir = data_root
            self.database_url = SecretStr(
                f"sqlite+pysqlite:///{(data_root / 'database' / 'contract-review.db').as_posix()}"
            )
            self.database_enabled = True
            self.upload_dir = data_root / "uploads"
            self.report_dir = data_root / "reports"
            self.contract_data_dir = data_root / "config" / "contracts"
            self.model_config_data_dir = data_root / "config" / "model-configs"
            self.prompt_template_data_dir = data_root / "config" / "prompt-templates"
            self.chat_data_dir = data_root / "config" / "chats"
            self.workflow_data_dir = data_root / "config" / "workflows"
            self.notification_data_dir = data_root / "config" / "notifications"
            self.security_data_dir = data_root / "config" / "security"
            self.review_task_data_dir = data_root / "config" / "review-tasks"
            self.rule_center_data_dir = data_root / "config" / "rule-center"
            self.knowledge_center_data_dir = data_root / "config" / "knowledge-center"
            self.risk_feedback_data_dir = data_root / "config" / "risk-feedback"
            self.review_tasks_sync_fallback = True
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
        if not self.database_enabled:
            raise ValueError("DATABASE_ENABLED must be true in production")
        if not self.redis_enabled:
            raise ValueError("REDIS_ENABLED must be true in production")
        if self.review_tasks_sync_fallback:
            raise ValueError("REVIEW_TASKS_SYNC_FALLBACK must be false in production")
        if not self.allowed_origins or any(
            origin == "*" or not origin.startswith("https://") for origin in self.allowed_origins
        ):
            raise ValueError("ALLOWED_ORIGINS must contain explicit HTTPS origins in production")
        if not self.trusted_hosts or "*" in self.trusted_hosts:
            raise ValueError("TRUSTED_HOSTS must contain explicit hosts in production")
        if self.trust_proxy_headers and not self.trusted_proxy_cidrs:
            raise ValueError("TRUSTED_PROXY_CIDRS is required when proxy headers are trusted")
        try:
            for cidr in self.trusted_proxy_cidrs:
                ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError("TRUSTED_PROXY_CIDRS contains an invalid network") from exc
        return self

    @field_validator("allowed_origins", "trusted_hosts", "trusted_proxy_cidrs", mode="before")
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
