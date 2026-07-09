from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage


class ContractReviewState(TypedDict, total=False):
    review_id: str
    file_path: str
    file_name: str
    file_type: str | None
    raw_text: str
    llm_config: dict[str, Any]
    extracted_fields: dict[str, Any]
    compliance_findings: list[dict[str, Any]]
    risk_summary: dict[str, Any]
    revision_suggestions: list[dict[str, Any]]
    final_report: dict[str, Any]
    agent_trace: list[dict[str, Any]]
    messages: list[BaseMessage]
    next_step: Literal["extractor", "finish"]
    errors: list[str]
