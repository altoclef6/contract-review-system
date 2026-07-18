from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from contract_review.core.config import Settings
from contract_review.database.models import RiskFindingModel
from contract_review.database.session import get_session_factory
from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.schemas.risk import (
    RiskComment,
    RiskListResponse,
    RiskRecord,
    RiskSource,
    RiskStateEvent,
    RiskStatistics,
    RiskStatus,
)
from contract_review.services.contract_service import ContractService, ContractServiceError
from contract_review.services.user_service import UserService


class RiskServiceError(ValueError):
    pass


class RiskConflictError(RiskServiceError):
    pass


class RiskPermissionError(RiskServiceError):
    pass


class RiskTransitionError(RiskServiceError):
    pass


TRANSITIONS: dict[RiskStatus, set[RiskStatus]] = {
    RiskStatus.pending_review: {RiskStatus.confirmed, RiskStatus.rejected},
    RiskStatus.confirmed: {RiskStatus.remediating, RiskStatus.closed},
    RiskStatus.rejected: {RiskStatus.closed},
    RiskStatus.remediating: {RiskStatus.remediated},
    RiskStatus.remediated: {RiskStatus.remediating, RiskStatus.closed},
    RiskStatus.closed: set(),
}


class RiskService:
    _lock = threading.Lock()

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.contract_data_dir / "risks.json"
        self.store = JsonDocumentStore(self.path, "risk_findings_ledger")

    def persist_review_findings(
        self,
        *,
        review_id: str,
        findings: list[dict[str, Any]],
        contract_id: str | None,
        contract_version_id: str | None,
        created_by: str | None,
    ) -> list[RiskRecord]:
        now = self._now()
        records = [
            self._from_finding(
                item,
                review_id=review_id,
                contract_id=contract_id,
                contract_version_id=contract_version_id,
                created_by=created_by,
                now=now,
            )
            for item in findings
        ]
        if self.settings.database_enabled:
            with get_session_factory()() as session, session.begin():
                existing = set(
                    session.scalars(
                        select(RiskFindingModel.source_risk_id).where(
                            RiskFindingModel.review_task_id == review_id
                        )
                    ).all()
                )
                for record in records:
                    if record.source_risk_id not in existing:
                        session.add(self._to_model(record))
            return records
        with self._lock:
            current = self._load_local()
            existing_keys: set[tuple[str, str | None]] = {
                (item.review_id, item.source_risk_id) for item in current
            }
            additions = [
                item
                for item in records
                if (item.review_id, item.source_risk_id) not in existing_keys
            ]
            if additions:
                self._save_local(current + additions)
            return additions

    def list_risks(
        self,
        *,
        page: int,
        page_size: int,
        actor_id: str,
        actor_role: str,
        keyword: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        status: RiskStatus | None = None,
        assignee_id: str | None = None,
        contract_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        review_id: str | None = None,
    ) -> RiskListResponse:
        records = self._load_all()
        if actor_role != "admin":
            records = [
                item
                for item in records
                if item.created_by == actor_id or item.assignee_id == actor_id
            ]
        records = [self._enrich(item) for item in records]
        if keyword:
            term = keyword.casefold()
            records = [
                item
                for item in records
                if term in item.title.casefold()
                or term in (item.contract_title or "").casefold()
                or term in item.matched_text.casefold()
            ]
        if severity:
            records = [item for item in records if item.severity == severity]
        if category:
            records = [item for item in records if item.category == category]
        if status:
            records = [item for item in records if item.status == status]
        if assignee_id:
            records = [item for item in records if item.assignee_id == assignee_id]
        if contract_type:
            records = [item for item in records if item.contract_type == contract_type]
        if review_id:
            records = [item for item in records if item.review_id == review_id]
        if date_from:
            records = [item for item in records if item.created_at >= date_from]
        if date_to:
            records = [item for item in records if item.created_at <= date_to]
        records.sort(key=lambda item: item.updated_at, reverse=True)
        total = len(records)
        start = (page - 1) * page_size
        return RiskListResponse(
            items=records[start : start + page_size], total=total, page=page, page_size=page_size
        )

    def statistics(self, *, actor_id: str, actor_role: str) -> RiskStatistics:
        records = self._load_all()
        if actor_role != "admin":
            records = [
                item
                for item in records
                if item.created_by == actor_id or item.assignee_id == actor_id
            ]
        enriched = [self._enrich(item) for item in records]

        def count_by(values: list[str], fallback: str = "未知") -> dict[str, int]:
            result: dict[str, int] = {}
            for value in values:
                key = value or fallback
                result[key] = result.get(key, 0) + 1
            return result

        scores = [item.risk_score for item in enriched]
        return RiskStatistics(
            total=len(enriched),
            pending_review_count=sum(
                item.status == RiskStatus.pending_review for item in enriched
            ),
            active_remediation_count=sum(
                item.status == RiskStatus.remediating for item in enriched
            ),
            resolved_count=sum(
                item.status in {RiskStatus.remediated, RiskStatus.closed} for item in enriched
            ),
            ai_involved_count=sum(item.ai_involved for item in enriched),
            average_risk_score=round(sum(scores) / len(scores), 2) if scores else 0,
            severities=count_by([item.severity for item in enriched]),
            statuses=count_by([item.status.value for item in enriched]),
            categories=count_by([item.category for item in enriched]),
            contract_types=count_by([item.contract_type or "未关联合同" for item in enriched]),
        )

    def get(self, risk_id: str, *, actor_id: str, actor_role: str) -> RiskRecord:
        record = self._find(risk_id)
        if (
            actor_role != "admin"
            and record.created_by != actor_id
            and record.assignee_id != actor_id
        ):
            raise RiskServiceError("风险不存在或不可访问")
        return self._enrich(record)

    def list_by_review(self, review_id: str) -> list[RiskRecord]:
        return [self._enrich(item) for item in self._load_all() if item.review_id == review_id]

    def transition(
        self,
        risk_id: str,
        *,
        target: RiskStatus,
        actor_id: str,
        actor_role: str,
        expected_revision: int,
        reason: str | None,
    ) -> tuple[RiskRecord, RiskStatus]:
        def update(record: RiskRecord) -> None:
            if actor_role not in {"admin", "legal"} and target in {
                RiskStatus.confirmed,
                RiskStatus.rejected,
                RiskStatus.closed,
            }:
                raise RiskPermissionError("当前角色不能执行该复核操作")
            if target not in TRANSITIONS[record.status]:
                raise RiskTransitionError(
                    f"风险状态不能从 {record.status.value} 流转到 {target.value}"
                )
            old = record.status
            record.status = target
            record.reviewer_id = actor_id
            record.review_comment = reason or record.review_comment
            now = self._now()
            if target == RiskStatus.confirmed:
                record.confirmed_at = now
            if target in {RiskStatus.remediated, RiskStatus.closed}:
                record.resolved_at = now
            record.state_history.append(
                RiskStateEvent(
                    event_id=f"event_{uuid4().hex}",
                    actor_id=actor_id,
                    old_status=old,
                    new_status=target,
                    reason=reason,
                    created_at=now,
                )
            )

        current = self.get(risk_id, actor_id=actor_id, actor_role=actor_role)
        old_status = current.status
        return self._mutate(risk_id, expected_revision, update), old_status

    def assign(
        self,
        risk_id: str,
        *,
        assignee_id: str | None,
        actor_id: str,
        actor_role: str,
        expected_revision: int,
    ) -> RiskRecord:
        if actor_role not in {"admin", "legal"}:
            raise RiskPermissionError("当前角色不能分配风险")
        if assignee_id and UserService(self.settings).get_by_id(assignee_id) is None:
            raise RiskServiceError("负责人不存在")
        self.get(risk_id, actor_id=actor_id, actor_role=actor_role)
        return self._mutate(
            risk_id, expected_revision, lambda record: setattr(record, "assignee_id", assignee_id)
        )

    def add_comment(
        self,
        risk_id: str,
        *,
        content: str,
        actor_id: str,
        actor_role: str,
        expected_revision: int,
    ) -> RiskRecord:
        self.get(risk_id, actor_id=actor_id, actor_role=actor_role)

        def update(record: RiskRecord) -> None:
            record.comments.append(
                RiskComment(
                    comment_id=f"comment_{uuid4().hex}",
                    author_id=actor_id,
                    content=content.strip(),
                    created_at=self._now(),
                )
            )

        return self._mutate(risk_id, expected_revision, update)

    def save_revision(
        self,
        risk_id: str,
        *,
        revised_clause: str,
        actor_id: str,
        actor_role: str,
        expected_revision: int,
    ) -> RiskRecord:
        self.get(risk_id, actor_id=actor_id, actor_role=actor_role)
        return self._mutate(
            risk_id,
            expected_revision,
            lambda record: setattr(record, "revised_clause", revised_clause.strip()),
        )

    def _mutate(
        self, risk_id: str, expected_revision: int, update: Callable[[RiskRecord], None]
    ) -> RiskRecord:
        if self.settings.database_enabled:
            with get_session_factory()() as session, session.begin():
                model = session.scalar(
                    select(RiskFindingModel).where(RiskFindingModel.id == risk_id).with_for_update()
                )
                if model is None:
                    raise RiskServiceError("风险不可访问")
                record = self._from_model(model)
                if record.revision != expected_revision:
                    raise RiskConflictError("风险已被其他用户更新，请刷新后重试")
                update(record)
                record.revision += 1
                record.updated_at = self._now()
                self._apply_model(model, record)
                session.flush()
                return self._enrich(record)
        with self._lock:
            records = self._load_local()
            index = next((i for i, item in enumerate(records) if item.risk_id == risk_id), None)
            if index is None:
                raise RiskServiceError("风险不可访问")
            record = records[index].model_copy(deep=True)
            if record.revision != expected_revision:
                raise RiskConflictError("风险已被其他用户更新，请刷新后重试")
            update(record)
            record.revision += 1
            record.updated_at = self._now()
            records[index] = record
            self._save_local(records)
            return self._enrich(record)

    def _load_all(self) -> list[RiskRecord]:
        if self.settings.database_enabled:
            with get_session_factory()() as session:
                return [
                    self._from_model(item)
                    for item in session.scalars(select(RiskFindingModel)).all()
                ]
        return self._load_local()

    def _find(self, risk_id: str) -> RiskRecord:
        for item in self._load_all():
            if item.risk_id == risk_id:
                return item
        raise RiskServiceError("风险不可访问")

    def _load_local(self) -> list[RiskRecord]:
        data = self.store.read([])
        if not isinstance(data, list):
            return []
        return [RiskRecord.model_validate(item) for item in data]

    def _save_local(self, records: list[RiskRecord]) -> None:
        self.store.write(
            [
                item.model_dump(
                    mode="json",
                    exclude={
                        "contract_title",
                        "contract_type",
                        "contract_version",
                        "assignee_name",
                    },
                )
                for item in records
            ]
        )

    def _from_finding(
        self,
        item: dict[str, Any],
        *,
        review_id: str,
        contract_id: str | None,
        contract_version_id: str | None,
        created_by: str | None,
        now: datetime,
    ) -> RiskRecord:
        raw_location: dict[str, Any] = (
            item["原文定位"] if isinstance(item.get("原文定位"), dict) else {}
        )
        source_value = str(item.get("来源") or item.get("source") or "deterministic_rule")
        ai_involved = "AI" in source_value or source_value == "llm_analysis"
        source = RiskSource.llm_analysis if ai_involved else RiskSource.deterministic_rule
        confidence = item.get("confidence")
        severity = str(item.get("风险等级") or item.get("severity") or "中")
        event = RiskStateEvent(
            event_id=f"event_{uuid4().hex}",
            actor_id=created_by or "system",
            new_status=RiskStatus.pending_review,
            reason="审查发现风险",
            created_at=now,
        )
        return RiskRecord(
            risk_id=f"risk_{uuid4().hex}",
            source_risk_id=str(item.get("风险编号") or item.get("risk_id") or uuid4().hex),
            contract_id=contract_id,
            contract_version_id=contract_version_id,
            review_id=review_id,
            severity=severity,
            category=str(item.get("风险类别") or item.get("category") or "其他"),
            title=str(item.get("风险标题") or item.get("title") or "未命名风险"),
            matched_text=str(item.get("相关条款") or item.get("contract_text") or ""),
            normalized_text=str(item.get("normalized_text") or ""),
            start_offset=_int_or_none(item.get("start_offset", raw_location.get("字符起点"))),
            end_offset=_int_or_none(item.get("end_offset", raw_location.get("字符终点"))),
            page_number=_int_or_none(item.get("page_number", raw_location.get("页码"))),
            paragraph_index=_int_or_none(item.get("paragraph_index")),
            bounding_box=item.get("bounding_box")
            if isinstance(item.get("bounding_box"), list)
            else None,
            rule_id=_string_or_none(item.get("rule_id")),
            knowledge_document_ids=[str(value) for value in item.get("knowledge_document_ids", [])],
            legal_basis=item.get("legal_basis", [])
            if isinstance(item.get("legal_basis"), list)
            else [],
            detection_source=source,
            ai_involved=ai_involved,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            risk_score=float(item.get("risk_score") or _severity_score(severity)),
            explanation=str(item.get("问题说明") or item.get("explanation") or ""),
            recommendation=str(item.get("修改方向") or item.get("recommendation") or ""),
            created_by=created_by,
            created_at=now,
            updated_at=now,
            state_history=[event],
        )

    def _enrich(self, record: RiskRecord) -> RiskRecord:
        updates: dict[str, Any] = {}
        if record.contract_id:
            try:
                contract = ContractService(self.settings.contract_data_dir).get_contract(
                    record.contract_id
                )
                updates.update(contract_title=contract.title, contract_type=contract.category.value)
                if record.contract_version_id:
                    updates["contract_version"] = (
                        ContractService(self.settings.contract_data_dir)
                        .get_version(record.contract_id, record.contract_version_id)
                        .version_no
                    )
            except ContractServiceError:
                pass
        if record.assignee_id:
            user = UserService(self.settings).get_by_id(record.assignee_id)
            updates["assignee_name"] = user.full_name if user else record.assignee_id
        return record.model_copy(update=updates)

    def _to_model(self, record: RiskRecord) -> RiskFindingModel:
        model = RiskFindingModel(id=record.risk_id)
        self._apply_model(model, record)
        return model

    def _apply_model(self, model: RiskFindingModel, record: RiskRecord) -> None:
        model.contract_id = record.contract_id
        model.contract_version_id = record.contract_version_id
        model.review_task_id = record.review_id
        model.source_risk_id = record.source_risk_id
        model.title = record.title
        model.category = record.category
        model.severity = record.severity
        model.risk_score = record.risk_score
        model.source = record.detection_source.value
        model.confidence = record.confidence
        model.contract_text = record.matched_text
        model.normalized_text = record.normalized_text
        model.location = {
            "start_offset": record.start_offset,
            "end_offset": record.end_offset,
            "page_number": record.page_number,
            "paragraph_index": record.paragraph_index,
            "bounding_box": record.bounding_box,
        }
        model.explanation = record.explanation
        model.legal_basis = record.legal_basis
        model.recommendation = record.recommendation
        model.suggested_revision = None
        model.requires_human_review = True
        model.agent_name = None
        model.rule_id = record.rule_id
        model.knowledge_document_ids = record.knowledge_document_ids
        model.status = record.status.value
        model.reviewer_comment = record.review_comment
        model.ai_original_recommendation = record.recommendation
        model.human_final_opinion = None
        model.revised_clause = record.revised_clause
        model.assignee_id = record.assignee_id
        model.reviewer_id = record.reviewer_id
        model.created_by = record.created_by
        model.confirmed_at = record.confirmed_at
        model.resolved_at = record.resolved_at
        model.revision = record.revision
        model.state_history = [item.model_dump(mode="json") for item in record.state_history]
        model.comments = [item.model_dump(mode="json") for item in record.comments]
        model.ai_involved = record.ai_involved
        model.created_at = record.created_at
        model.updated_at = record.updated_at

    def _from_model(self, model: RiskFindingModel) -> RiskRecord:
        location = model.location or {}
        return RiskRecord(
            risk_id=model.id,
            source_risk_id=model.source_risk_id,
            contract_id=model.contract_id,
            contract_version_id=model.contract_version_id,
            review_id=model.review_task_id,
            severity=model.severity,
            category=model.category,
            title=model.title,
            matched_text=model.contract_text,
            normalized_text=model.normalized_text,
            start_offset=location.get("start_offset"),
            end_offset=location.get("end_offset"),
            page_number=location.get("page_number"),
            paragraph_index=location.get("paragraph_index"),
            bounding_box=location.get("bounding_box"),
            rule_id=model.rule_id,
            knowledge_document_ids=model.knowledge_document_ids or [],
            legal_basis=model.legal_basis or [],
            detection_source=RiskSource(model.source),
            ai_involved=model.ai_involved,
            confidence=model.confidence,
            risk_score=model.risk_score,
            explanation=model.explanation,
            recommendation=model.recommendation,
            status=RiskStatus(model.status),
            assignee_id=model.assignee_id,
            reviewer_id=model.reviewer_id,
            review_comment=model.reviewer_comment,
            revised_clause=model.revised_clause,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            confirmed_at=model.confirmed_at,
            resolved_at=model.resolved_at,
            revision=model.revision,
            state_history=[
                RiskStateEvent.model_validate(item) for item in model.state_history or []
            ],
            comments=[RiskComment.model_validate(item) for item in model.comments or []],
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


def _severity_score(value: str) -> float:
    return {
        "低": 25,
        "中": 50,
        "高": 75,
        "严重": 95,
        "low": 25,
        "medium": 50,
        "high": 75,
        "critical": 95,
    }.get(value, 50)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
