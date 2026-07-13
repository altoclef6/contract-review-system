from __future__ import annotations

from typing import Any, Literal

AgentModelRole = Literal["extraction", "compliance", "refinement"]

_DEEPSEEK_V4_ROLE_MODELS: dict[AgentModelRole, str] = {
    "extraction": "deepseek-v4-flash",
    "compliance": "deepseek-v4-pro",
    "refinement": "deepseek-v4-flash",
}


def route_model_config(
    config: dict[str, Any] | None,
    *,
    role: AgentModelRole | None,
    default_provider: str,
    default_model_name: str,
) -> dict[str, Any] | None:
    """Select a role-specific model without mutating stored credentials.

    A DeepSeek V4 Pro configuration acts as the quality anchor. Extraction and
    refinement use V4 Flash for lower latency, while compliance keeps V4 Pro.
    Other providers and explicitly selected non-Pro DeepSeek models are left
    untouched.
    """
    if role is None:
        return config

    routed = dict(config or {})
    provider = str(routed.get("provider") or default_provider)
    model_name = str(routed.get("model_name") or default_model_name)
    if provider != "deepseek" or model_name != "deepseek-v4-pro":
        return config

    routed["provider"] = provider
    routed["model_name"] = _DEEPSEEK_V4_ROLE_MODELS[role]
    return routed
