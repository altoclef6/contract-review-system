from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from contract_review.core.config import Settings
from contract_review.schemas.reader import (
    ReaderChapter,
    ReaderKnowledgeBasis,
    ReaderRisk,
    ReaderRiskLocation,
    ReaderWorkspace,
    ReaderWorkspaceSummary,
)
from contract_review.services.contract_service import ContractService, ContractServiceError
from contract_review.services.document_loader import DocumentLoader
from contract_review.services.risk_service import RiskService
from contract_review.services.user_service import UserService


class ReaderWorkspaceError(ValueError):
    pass


def resolve_text_location(
    text: str,
    clause_text: str,
    *,
    start_offset: Any = None,
    end_offset: Any = None,
    paragraph_index: Any = None,
) -> ReaderRiskLocation:
    """Resolve against immutable original text without inventing coordinates."""
    clause = clause_text.strip()
    try:
        start = int(start_offset) if start_offset is not None else None
        end = int(end_offset) if end_offset is not None else None
    except (TypeError, ValueError):
        start = end = None
    if start is not None and end is not None and 0 <= start < end <= len(text):
        selected = text[start:end]
        if not clause or selected == clause or clause in selected or selected in clause:
            return ReaderRiskLocation(
                status="exact_offset",
                start_offset=start,
                end_offset=end,
                paragraph_index=_safe_int(paragraph_index),
            )
    if not text or not clause or clause.startswith("未在合同文本中"):
        return ReaderRiskLocation(status="unavailable")

    occurrences = [match.start() for match in re.finditer(re.escape(clause), text)]
    paragraph = _safe_int(paragraph_index)
    if paragraph is not None and occurrences:
        ranges = _paragraph_ranges(text)
        if 0 <= paragraph < len(ranges):
            left, right = ranges[paragraph]
            match = next((value for value in occurrences if left <= value < right), None)
            if match is not None:
                return ReaderRiskLocation(
                    status="paragraph_match",
                    start_offset=match,
                    end_offset=match + len(clause),
                    paragraph_index=paragraph,
                    is_ambiguous=len(occurrences) > 1,
                )
    if occurrences:
        match = occurrences[0]
        return ReaderRiskLocation(
            status="text_match",
            start_offset=match,
            end_offset=match + len(clause),
            paragraph_index=_paragraph_at(text, match),
            is_ambiguous=len(occurrences) > 1,
        )
    return ReaderRiskLocation(status="unavailable")


class ReaderWorkspaceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, record: dict[str, Any]) -> ReaderWorkspace:
        report = self._load_report(record)
        contract_text = self._load_contract_text(record)
        raw_risks: list[Any] = (
            report["风险点"] if isinstance(report.get("风险点"), list) else []
        )
        knowledge_hits: list[Any] = (
            report["依据检索"] if isinstance(report.get("依据检索"), list) else []
        )
        suggestions = {
            str(item.get("对应风险编号")): item
            for item in report.get("修改建议", [])
            if isinstance(item, dict) and item.get("对应风险编号")
        }
        persisted = {
            item.source_risk_id: item
            for item in RiskService(self.settings).list_by_review(str(record.get("review_id")))
            if item.source_risk_id
        }
        risks = [
            self._normalize_risk(item, contract_text, knowledge_hits, suggestions, persisted)
            for item in raw_risks
            if isinstance(item, dict)
        ]
        contract_name = str(record.get("file_name") or report.get("文件名") or "未命名合同")
        contract_version: int | None = None
        contract_id = _optional_string(record.get("contract_id"))
        version_id = _optional_string(record.get("contract_version_id"))
        if contract_id:
            try:
                contract = ContractService(self.settings.contract_data_dir).get_contract(
                    contract_id
                )
                contract_name = contract.title
                if version_id:
                    contract_version = (
                        ContractService(self.settings.contract_data_dir)
                        .get_version(contract_id, version_id)
                        .version_no
                    )
            except ContractServiceError:
                pass
        operator_name = None
        actor_id = _optional_string(record.get("created_by"))
        if actor_id:
            operator = UserService(self.settings).get_by_id(actor_id)
            operator_name = operator.full_name if operator else None
        score = report.get("风险评分")
        risk_score = score.get("风险分") if isinstance(score, dict) else None
        source_path = Path(str(record.get("source_file_path") or ""))
        reviewed_value = record.get("created_at")
        if isinstance(reviewed_value, str):
            reviewed_value = datetime.fromisoformat(reviewed_value.replace("Z", "+00:00"))
        if not isinstance(reviewed_value, datetime):
            raise ReaderWorkspaceError("审查记录缺少有效创建时间")
        summary = ReaderWorkspaceSummary(
            review_id=str(record.get("review_id")),
            contract_id=contract_id,
            contract_version_id=version_id,
            contract_name=contract_name,
            contract_type=str(record.get("contract_type") or "general"),
            contract_version=contract_version,
            status="completed",
            reviewed_at=reviewed_value,
            operator_name=operator_name,
            overall_risk_level=_optional_string(report.get("总体风险等级")),
            risk_score=float(risk_score) if isinstance(risk_score, (int, float)) else None,
            risk_count=len(risks),
            report_available=bool(record.get("report_path") or record.get("exports")),
            source_is_pdf=source_path.suffix.lower() == ".pdf",
        )
        return ReaderWorkspace(
            summary=summary,
            contract_text=contract_text,
            risks=risks,
            chapters=_build_chapters(contract_text, risks),
        )

    def _load_report(self, record: dict[str, Any]) -> dict[str, Any]:
        path_value = record.get("exports", {}).get("json") or record.get("report_path")
        path = self._safe_path(path_value, self.settings.report_dir)
        if path is None or not path.is_file():
            raise ReaderWorkspaceError("审查报告不存在")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReaderWorkspaceError("审查报告无法读取") from exc
        return value if isinstance(value, dict) else {}

    def _load_contract_text(self, record: dict[str, Any]) -> str:
        text_path = self._safe_path(record.get("contract_text_path"), self.settings.report_dir)
        if text_path and text_path.is_file():
            return text_path.read_text(encoding="utf-8", errors="replace")
        source_path = self._safe_path(record.get("source_file_path"), self.settings.upload_dir)
        if source_path is None or not source_path.is_file():
            return ""
        try:
            return DocumentLoader(self.settings).load_text(source_path)
        except Exception:
            return ""

    def _safe_path(self, value: Any, root: Path) -> Path | None:
        if not value:
            return None
        path = Path(str(value)).resolve()
        if not path.is_relative_to(root.resolve()):
            return None
        return path

    def _normalize_risk(
        self,
        item: dict[str, Any],
        contract_text: str,
        knowledge_hits: list[Any],
        suggestions: dict[str, dict[str, Any]],
        persisted: dict[str, Any],
    ) -> ReaderRisk:
        source_risk_id = str(item.get("风险编号") or item.get("risk_id") or "未编号")
        saved = persisted.get(source_risk_id)
        clause = str(item.get("相关条款") or item.get("contract_text") or "")
        raw_location: dict[str, Any] = (
            item["原文定位"] if isinstance(item.get("原文定位"), dict) else {}
        )
        location = resolve_text_location(
            contract_text,
            clause or str(raw_location.get("定位文本") or ""),
            start_offset=item.get("start_offset", raw_location.get("字符起点")),
            end_offset=item.get("end_offset", raw_location.get("字符终点")),
            paragraph_index=item.get("paragraph_index"),
        )
        page = item.get("page_number") or raw_location.get("页码")
        bbox = item.get("bounding_box") or raw_location.get("坐标")
        location.page_number = _safe_positive_int(page)
        location.bounding_box = (
            [float(value) for value in bbox]
            if isinstance(bbox, list)
            and len(bbox) == 4
            and all(isinstance(value, (int, float)) for value in bbox)
            else None
        )
        source = str(item.get("来源") or item.get("source") or "规则审查")
        ai_involved = "AI" in source or source == "llm_analysis"
        confidence = item.get("confidence")
        suggestion = suggestions.get(source_risk_id, {})
        return ReaderRisk(
            risk_id=saved.risk_id if saved else source_risk_id,
            source_risk_id=source_risk_id,
            title=str(item.get("风险标题") or item.get("title") or "未命名风险"),
            category=str(item.get("风险类别") or item.get("category") or "其他"),
            severity=str(item.get("风险等级") or item.get("severity") or "中"),
            clause_text=clause,
            explanation=str(item.get("问题说明") or item.get("explanation") or ""),
            recommendation=str(
                item.get("修改方向")
                or item.get("recommendation")
                or suggestion.get("修改建议")
                or ""
            ),
            suggested_revision=_optional_string(
                item.get("suggested_revision") or suggestion.get("建议条款")
            ),
            source=source,
            rule_id=_optional_string(item.get("rule_id")),
            detection_method=(
                "LLM语义分析"
                if ai_involved
                else "确定性规则"
                if source == "deterministic_rule"
                else "规则审查"
            ),
            ai_involved=ai_involved,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            location=location,
            knowledge_basis=_verified_basis(item, knowledge_hits),
            status=saved.status.value if saved else "pending_review",
            revision=saved.revision if saved else 1,
            persisted=saved is not None,
            assignee_id=saved.assignee_id if saved else None,
            reviewer_id=saved.reviewer_id if saved else None,
            review_comment=saved.review_comment if saved else None,
            revised_clause=saved.revised_clause if saved else None,
        )


def _verified_basis(item: dict[str, Any], hits: list[Any]) -> list[ReaderKnowledgeBasis]:
    explicit_ids = {
        str(value) for value in item.get("knowledge_document_ids", []) if str(value).strip()
    }
    risk_text = " ".join(str(item.get(key) or "") for key in ("风险类别", "风险标题", "问题说明"))
    groups = {
        "付款": ("付款", "支付", "结算", "发票", "金额"),
        "验收": ("验收", "交付", "期限"),
        "数据": ("数据", "个人信息", "泄露", "保存", "删除", "权限"),
        "保密": ("保密", "商业秘密"),
        "责任": ("违约", "赔偿", "责任"),
        "争议": ("争议", "仲裁", "法院", "管辖"),
    }
    risk_words = {word for words in groups.values() for word in words if word in risk_text}
    results: list[ReaderKnowledgeBasis] = []
    for raw in hits:
        if (
            not isinstance(raw, dict)
            or not raw.get("document_id")
            or raw.get("status") != "effective"
        ):
            continue
        document_id = str(raw["document_id"])
        content = str(raw.get("内容") or "")
        if document_id not in explicit_ids and not any(word in content for word in risk_words):
            continue
        results.append(
            ReaderKnowledgeBasis(
                document_id=document_id,
                name=str(raw.get("来源") or document_id),
                article_number=_optional_string(raw.get("article_number")),
                source_type=str(raw.get("source_type") or "unknown"),
                status=str(raw.get("status")),
                updated_at=raw.get("updated_at") or None,
            )
        )
    return results


def _build_chapters(text: str, risks: list[ReaderRisk]) -> list[ReaderChapter]:
    if not text:
        return []
    heading = re.compile(
        r"(?m)^(\s*(?:第[一二三四五六七八九十百零0-9]+[章节条]|[0-9]+[.、])[^\n]{0,80})"
    )
    matches = list(heading.finditer(text))
    if not matches:
        return [
            ReaderChapter(
                chapter_id="chapter-1",
                title="合同全文",
                start_offset=0,
                end_offset=len(text),
                risk_count=len([risk for risk in risks if risk.location.start_offset is not None]),
                high_risk_count=sum(
                    risk.location.start_offset is not None
                    and risk.severity in {"高", "严重", "high", "critical"}
                    for risk in risks
                ),
            )
        ]
    chapters: list[ReaderChapter] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group(1).strip() if match.group(0) else "合同全文"
        contained = [
            risk
            for risk in risks
            if risk.location.start_offset is not None and start <= risk.location.start_offset < end
        ]
        chapters.append(
            ReaderChapter(
                chapter_id=f"chapter-{index + 1}",
                title=title or f"章节 {index + 1}",
                start_offset=start,
                end_offset=end,
                risk_count=len(contained),
                high_risk_count=sum(
                    risk.severity in {"高", "严重", "high", "critical"} for risk in contained
                ),
            )
        )
    return chapters


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"\n+", text):
        ranges.append((start, match.start()))
        start = match.end()
    ranges.append((start, len(text)))
    return ranges


def _paragraph_at(text: str, offset: int) -> int:
    return sum(1 for match in re.finditer(r"\n+", text[:offset]))


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_positive_int(value: Any) -> int | None:
    parsed = _safe_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _optional_string(value: Any) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None
