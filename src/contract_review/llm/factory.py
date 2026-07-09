from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from contract_review.core.config import Settings, get_settings
from contract_review.core.exceptions import LLMConfigurationError


def create_chat_model(settings: Settings | None = None, llm_config: dict[str, Any] | None = None) -> ChatOpenAI:
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

    kwargs = {
        "model": runtime_config.get("model_name") or resolved_settings.llm_model_name,
        "api_key": api_key,
        "temperature": resolved_settings.llm_temperature,
        "timeout": resolved_settings.llm_timeout_seconds,
    }
    base_url = runtime_config.get("base_url") or resolved_settings.resolve_llm_base_url()
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
