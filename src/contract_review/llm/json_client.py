from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from contract_review.core.config import get_settings
from contract_review.core.exceptions import LLMConfigurationError
from contract_review.core.metrics import metrics_registry
from contract_review.llm.factory import create_chat_model
from contract_review.services.model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates = [cleaned]
    object_match = re.search(r"\{.*\}", cleaned, flags=re.S)
    if object_match:
        candidates.append(object_match.group(0))
    array_match = re.search(r"\[.*\]", cleaned, flags=re.S)
    if array_match:
        candidates.append(array_match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    *,
    max_chars: int = 16000,
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any] | None:
    """Call the configured external LLM and parse a JSON response.

    The project must remain runnable without an API key, so all LLM errors are contained
    here and callers can fall back to deterministic rule-based logic.
    """
    settings = get_settings()
    if not settings.enable_llm:
        return None
    effective_llm_config = llm_config
    if not (effective_llm_config or {}).get("api_key"):
        active_config = ModelConfigService(
            settings.model_config_data_dir,
            settings.resolve_model_credential_encryption_key(),
        ).resolve_active_runtime_config()
        if active_config is not None:
            effective_llm_config = active_config.model_dump()

    if not (effective_llm_config or {}).get("api_key") and settings.resolve_llm_api_key() is None:
        return None

    try:
        model = create_chat_model(settings, effective_llm_config)
    except LLMConfigurationError:
        return None

    bounded_prompt = user_prompt[:max_chars]
    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=bounded_prompt),
            ]
        )
    except Exception as exc:  # pragma: no cover - external API behavior
        metrics_registry.record_ai_call(is_error=True)
        logger.warning("LLM call failed: %s", exc)
        return None
    metrics_registry.record_ai_call()

    content = getattr(response, "content", "")
    if isinstance(content, list):
        content = "\n".join(str(part) for part in content)
    if not isinstance(content, str):
        return None
    return _extract_json(content)


async def call_llm_text(
    system_prompt: str,
    messages: list[tuple[str, str]],
    *,
    max_chars: int = 24000,
    llm_config: dict[str, Any] | None = None,
) -> str | None:
    settings = get_settings()
    if not settings.enable_llm:
        return None
    effective_llm_config = llm_config
    if not (effective_llm_config or {}).get("api_key"):
        active_config = ModelConfigService(
            settings.model_config_data_dir,
            settings.resolve_model_credential_encryption_key(),
        ).resolve_active_runtime_config()
        if active_config is not None:
            effective_llm_config = active_config.model_dump()
    if not (effective_llm_config or {}).get("api_key") and settings.resolve_llm_api_key() is None:
        return None
    try:
        model = create_chat_model(settings, effective_llm_config)
    except LLMConfigurationError:
        return None
    request_messages = [SystemMessage(content=system_prompt)]
    used = 0
    for role, content in messages:
        bounded = content[: max(0, max_chars - used)]
        used += len(bounded)
        request_messages.append(
            HumanMessage(content=bounded)
            if role == "user"
            else SystemMessage(content=f"此前助手回答：{bounded}")
        )
        if used >= max_chars:
            break
    try:
        response = await model.ainvoke(request_messages)
    except Exception as exc:  # pragma: no cover - external API behavior
        metrics_registry.record_ai_call(is_error=True)
        logger.warning("LLM chat call failed: %s", exc)
        return None
    metrics_registry.record_ai_call()
    content = getattr(response, "content", "")
    if isinstance(content, list):
        content = "\n".join(str(part) for part in content)
    return content.strip() if isinstance(content, str) and content.strip() else None
