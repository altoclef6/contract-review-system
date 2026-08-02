from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage


class ContractReviewState(TypedDict, total=False):
    review_id: str
    file_path: str
    file_name: str
    file_type: str | None
    raw_text: str
    llm_config: dict[str, Any]
    contract_type: str
    contract_clauses: list[dict[str, Any]]
    classification: dict[str, Any]
    knowledge_hits: list[dict[str, Any]]
    node_telemetry: list[dict[str, Any]]
    prompt_templates: dict[str, str]
    extracted_fields: dict[str, Any]
    compliance_findings: list[dict[str, Any]]
    risk_summary: dict[str, Any]
    revision_suggestions: list[dict[str, Any]]
    final_report: dict[str, Any]
    agent_trace: list[dict[str, Any]]
    messages: list[BaseMessage]
    next_step: Literal["extractor", "finish"]
    errors: list[str]
    stage_callback: Callable[[str], None]


def emit_stage(state: ContractReviewState, stage: str) -> None:
    callback = state.get("stage_callback")
    if callable(callback):
        callback(stage)
