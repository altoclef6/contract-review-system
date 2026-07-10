from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, SecretStr


class ModelProvider(StrEnum):
    openai = "openai"
    deepseek = "deepseek"
    claude = "claude"
    gemini = "gemini"
    qwen = "qwen"
    openai_compatible = "openai_compatible"


class ModelProviderInfo(BaseModel):
    provider: ModelProvider
    label: str
    default_base_url: str | None = None
    default_model_name: str
    openai_compatible: bool


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: ModelProvider
    api_key: SecretStr = Field(min_length=8)
    base_url: str | None = Field(default=None, max_length=300)
    model_name: str = Field(min_length=1, max_length=120)
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=256, le=128000)
    description: str | None = Field(default=None, max_length=500)


class ModelConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    api_key: SecretStr | None = Field(default=None, min_length=8)
    base_url: str | None = Field(default=None, max_length=300)
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=256, le=128000)
    description: str | None = Field(default=None, max_length=500)


class ModelConfigPublic(BaseModel):
    id: str
    name: str
    provider: ModelProvider
    api_key_masked: str
    base_url: str | None = None
    model_name: str
    temperature: float
    max_tokens: int
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class ActiveModelConfig(BaseModel):
    config: ModelConfigPublic | None


class ModelRuntimeConfig(BaseModel):
    provider: ModelProvider
    api_key: str
    base_url: str | None = None
    model_name: str
    temperature: float
    max_tokens: int
