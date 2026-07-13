
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from contract_review.schemas.contract_management import (
    ClauseDiff,
    RiskRemediationMapping,
    VersionComparison,
)
from contract_review.schemas.version_comparison import (
    RiskChangeStatus,
    RiskComparison,
    TextChangeType,
    TextDiffSegment,
    VersionComparisonResult,
)

SEVERITY_WEIGHT = {
    "低": 1,
    "low": 1,
    "中": 2,
    "medium": 2,
    "高": 3,
    "high": 3,
    "严重": 4,
    "critical": 4,
}


class VersionComparisonError(ValueError):
    pass


class VersionComparisonService:
    def compare(
        self,
        *,
        from_version_id: str,
        to_version_id: str,
        old_text: str,
        new_text: str,
        old_risks: list[dict[str, str]] | None = None,
    ) -> VersionComparison:
        old_clauses = self._paragraphs(old_text)
        new_clauses = self._paragraphs(new_text)
        matcher = SequenceMatcher(a=old_clauses, b=new_clauses, autojunk=False)
        diffs: list[ClauseDiff] = []
        for operation, old_start, old_end, new_start, new_end in matcher.get_opcodes():
            if operation == "equal":
                diffs.extend(
                    ClauseDiff(operation="unchanged", text=value)
                    for value in old_clauses[old_start:old_end]
                )
            elif operation == "delete":
                diffs.extend(
                    ClauseDiff(operation="deleted", text=value)
                    for value in old_clauses[old_start:old_end]
                )
            elif operation == "insert":
                diffs.extend(
                    ClauseDiff(operation="added", text=value)
                    for value in new_clauses[new_start:new_end]
                )
            else:
                diffs.extend(
                    ClauseDiff(operation="deleted", text=value)
                    for value in old_clauses[old_start:old_end]
                )
                diffs.extend(
                    ClauseDiff(operation="added", text=value)
                    for value in new_clauses[new_start:new_end]
                )
        mappings = [self._map_legacy_risk(risk, new_text) for risk in old_risks or []]
        return VersionComparison(
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            clause_diffs=diffs,
            risk_mappings=mappings,
        )

    def compare_snapshots(
        self,
        *,
        contract_id: str,
        base_version: dict[str, Any],
        target_version: dict[str, Any],
    ) -> VersionComparisonResult:
        if base_version["id"] == target_version["id"]:
            raise VersionComparisonError("请选择两个不同版本")
        base_text = str(base_version.get("text_content") or "")
        target_text = str(target_version.get("text_content") or "")
        segments = self.compare_text(base_text, target_text)
        risk_changes = self.compare_risks(
            list(base_version.get("risk_snapshot") or []),
            list(target_version.get("risk_snapshot") or []),
        )
        summary: dict[str, int] = {}
        for segment in segments:
            summary[segment.change_type.value] = summary.get(segment.change_type.value, 0) + 1
        for change in risk_changes:
            key = f"risk_{change.status.value}"
            summary[key] = summary.get(key, 0) + 1
        return VersionComparisonResult(
            contract_id=contract_id,
            base_version_id=base_version["id"],
            target_version_id=target_version["id"],
            text_segments=segments,
            risk_changes=risk_changes,
            summary=summary,
        )

    def compare_text(self, base_text: str, target_text: str) -> list[TextDiffSegment]:
        base = self._paragraphs(base_text)
        target = self._paragraphs(target_text)
        matcher = SequenceMatcher(a=base, b=target, autojunk=False)
        result: list[TextDiffSegment] = []
        for operation, a1, a2, b1, b2 in matcher.get_opcodes():
            if operation == "equal":
                for offset, text in enumerate(base[a1:a2]):
                    result.append(
                        TextDiffSegment(
                            change_type=TextChangeType.unchanged,
                            base_index=a1 + offset,
                            target_index=b1 + offset,
                            base_text=text,
                            target_text=text,
                        )
                    )
            elif operation == "delete":
                result.extend(
                    TextDiffSegment(
                        change_type=TextChangeType.removed, base_index=index, base_text=base[index]
                    )
                    for index in range(a1, a2)
                )
            elif operation == "insert":
                result.extend(
                    TextDiffSegment(
                        change_type=TextChangeType.added,
                        target_index=index,
                        target_text=target[index],
                    )
                    for index in range(b1, b2)
                )
            else:
                size = max(a2 - a1, b2 - b1)
                for offset in range(size):
                    base_value = base[a1 + offset] if a1 + offset < a2 else ""
                    target_value = target[b1 + offset] if b1 + offset < b2 else ""
                    change_type = (
                        TextChangeType.modified
                        if base_value and target_value
                        else TextChangeType.removed
                        if base_value
                        else TextChangeType.added
                    )
                    result.append(
                        TextDiffSegment(
                            change_type=change_type,
                            base_index=a1 + offset if base_value else None,
                            target_index=b1 + offset if target_value else None,
                            base_text=base_value,
                            target_text=target_value,
                        )
                    )
        return result

    def compare_risks(
        self, base_risks: list[dict[str, Any]], target_risks: list[dict[str, Any]]
    ) -> list[RiskComparison]:
        candidates: list[tuple[float, int, int]] = []
        for base_index, base in enumerate(base_risks):
            for target_index, target in enumerate(target_risks):
                candidates.append((self._risk_similarity(base, target), base_index, target_index))
        candidates.sort(reverse=True)
        matched_base: set[int] = set()
        matched_target: set[int] = set()
        result: list[RiskComparison] = []
        for score, base_index, target_index in candidates:
            if score < 0.55 or base_index in matched_base or target_index in matched_target:
                continue
            matched_base.add(base_index)
            matched_target.add(target_index)
            base = base_risks[base_index]
            target = target_risks[target_index]
            if score < 0.8:
                status = RiskChangeStatus.uncertain_match
                explanation = "相似度不足以确认是同一风险，需要人工核对。"
            else:
                base_severity = SEVERITY_WEIGHT.get(
                    str(self._value(base, "severity", "风险等级")), 0
                )
                target_severity = SEVERITY_WEIGHT.get(
                    str(self._value(target, "severity", "风险等级")), 0
                )
                base_text = str(self._value(base, "matched_text", "相关条款", "命中原文") or "")
                target_text = str(self._value(target, "matched_text", "相关条款", "命中原文") or "")
                if target_severity > base_severity:
                    status, explanation = (
                        RiskChangeStatus.severity_increased,
                        "同类风险在目标版本中的等级上升。",
                    )
                elif target_severity < base_severity:
                    status, explanation = (
                        RiskChangeStatus.severity_decreased,
                        "同类风险在目标版本中的等级下降。",
                    )
                elif base_text != target_text:
                    status, explanation = (
                        RiskChangeStatus.text_changed,
                        "风险对应条款发生变化，风险是否解决仍需人工确认。",
                    )
                else:
                    status, explanation = (
                        RiskChangeStatus.unchanged,
                        "规则、类别、等级和命中文本保持一致。",
                    )
            result.append(
                RiskComparison(
                    status=status,
                    match_score=round(score, 4),
                    base_risk=base,
                    target_risk=target,
                    explanation=explanation,
                )
            )
        for index, risk in enumerate(base_risks):
            if index not in matched_base:
                explicit = str(risk.get("status", "")) == "remediated"
                result.append(
                    RiskComparison(
                        status=RiskChangeStatus.remediated
                        if explicit
                        else RiskChangeStatus.removed,
                        base_risk=risk,
                        explanation="风险在目标版本中未再次识别；可能已整改，但除非已有人工整改状态，否则不能自动确认。",
                    )
                )
        for index, risk in enumerate(target_risks):
            if index not in matched_target:
                result.append(
                    RiskComparison(
                        status=RiskChangeStatus.added,
                        target_risk=risk,
                        explanation="目标版本中新识别到的风险。",
                    )
                )
        return result

    def _risk_similarity(self, base: dict[str, Any], target: dict[str, Any]) -> float:
        score = 0.0
        base_rule = self._value(base, "rule_id", "规则编号")
        target_rule = self._value(target, "rule_id", "规则编号")
        if base_rule and target_rule and base_rule == target_rule:
            score += 0.45
        if self._value(base, "category", "风险类别") == self._value(target, "category", "风险类别"):
            score += 0.2
        base_text = str(self._value(base, "matched_text", "相关条款", "命中原文") or "")
        target_text = str(self._value(target, "matched_text", "相关条款", "命中原文") or "")
        if base_text or target_text:
            score += SequenceMatcher(None, base_text, target_text, autojunk=False).ratio() * 0.25
        base_section = self._value(base, "section", "章节", "clause_number")
        target_section = self._value(target, "section", "章节", "clause_number")
        if base_section and target_section and base_section == target_section:
            score += 0.05
        base_position = self._position(base)
        target_position = self._position(target)
        if base_position is not None and target_position is not None:
            score += max(0.0, 0.05 - min(abs(base_position - target_position), 10000) / 200000)
        return min(score, 1.0)

    def _map_legacy_risk(
        self, risk: dict[str, str], new_text: str
    ) -> RiskRemediationMapping:
        old_clause = risk.get("contract_text", "").strip()
        risk_id = risk.get("risk_id", "unknown")
        tokens = [
            token
            for token in old_clause.replace("。", " ").replace("，", " ").split()
            if len(token) >= 4
        ]
        if old_clause and old_clause in new_text:
            status, new_clause = "unresolved", old_clause
        elif old_clause and any(token in new_text for token in tokens):
            status = "partially_resolved"
            new_clause = next((token for token in tokens if token in new_text), None)
        else:
            status, new_clause = "resolved", None
        return RiskRemediationMapping(
            risk_id=risk_id,
            status=status,
            old_text=old_clause,
            new_text=new_clause,
        )

    def _paragraphs(self, text: str) -> list[str]:
        return [
            part.strip()
            for part in re.split(r"\n\s*\n|(?=第[一二三四五六七八九十百零0-9]+条)", text)
            if part.strip()
        ]

    def _position(self, risk: dict[str, Any]) -> int | None:
        value = self._value(risk, "start_offset", "字符起点")
        if value is None and isinstance(risk.get("原文定位"), dict):
            value = risk["原文定位"].get("字符起点")
        return int(value) if isinstance(value, int | float) else None

    def _value(self, item: dict[str, Any], *keys: str) -> Any:
        return next((item[key] for key in keys if item.get(key) is not None), None)
