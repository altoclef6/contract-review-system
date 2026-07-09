from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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

    upload_dir: Path = Path("data/uploads")
    report_dir: Path = Path("data/reports")
    max_upload_size_mb: int = 50

    llm_provider: Literal["openai", "openai_compatible", "deepseek"] = "openai_compatible"
    llm_model_name: str = "gpt-4.1-mini"
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 60
    enable_llm: bool = True

    tesseract_cmd: str | None = None
    tessdata_dir: Path | None = None
    ocr_languages: str = "chi_sim+eng"

    @field_validator("allowed_origins", mode="before")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
