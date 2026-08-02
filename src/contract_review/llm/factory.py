from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from contract_review.core.config import Settings, get_settings
from contract_review.core.exceptions import LLMConfigurationError


def create_chat_model(
    settings: Settings | None = None,
    llm_config: dict[str, Any] | None = None,
) -> BaseChatModel:
    """Create an OpenAI-compatible chat model client from environment settings.

    This project intentionally calls external API providers only. It does not load local
    model weights, tokenizers, quantized files, or GPU inference runtimes.
    """
    resolved_settings = settings or get_settings()
    runtime_config = llm_config or {}
    api_key = runtime_config.get("api_key") or resolved_settings.resolve_llm_api_key()
    if api_key is None:
        raise LLMConfigurationError(
            "Missing external LLM API key. Set LLM_API_KEY, OPENAI_API_KEY, or DEEPSEEK_API_KEY."
        )
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()

    provider = runtime_config.get("provider") or resolved_settings.llm_provider
    kwargs: dict[str, Any] = {
        "model": runtime_config.get("model_name") or resolved_settings.llm_model_name,
        "temperature": runtime_config.get("temperature", resolved_settings.llm_temperature),
        "timeout": int(runtime_config.get("timeout_seconds", resolved_settings.llm_timeout_seconds)),
    }
    if runtime_config.get("max_tokens"):
        kwargs["max_tokens"] = int(runtime_config["max_tokens"])
    base_url = runtime_config.get("base_url") or resolved_settings.resolve_llm_base_url()
    if provider == "claude":
        kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url.removesuffix("/v1")
        return ChatAnthropic(**kwargs)

    kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
