
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract_review.infrastructure.document_store import JsonDocumentStore
from contract_review.rules import default_registry
from contract_review.rules.models import RuleDefinition, Severity
from contract_review.schemas.rule_center import RuleRecord, RuleUpdate
from contract_review.services.risk_feedback_service import RiskFeedbackService

RULE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "DET-PARTY-001",
        "title": "合同主体信息不完整",
        "name": "合同主体完整性",
        "category": "主体信息",
        "severity": "high",
        "logic": "结构化主体少于两个",
        "recommendation": "补充双方完整名称、统一社会信用代码、注册地址、联系人及授权代表。",
    },
    {
        "rule_id": "DET-AMOUNT-001",
        "title": "合同金额不明确",
        "name": "合同金额明确性",
        "category": "交易金额",
        "severity": "medium",
        "logic": "未提取到金额或价款计算方式",
        "recommendation": "明确合同总价、税率、含税口径、付款节点和结算依据。",
    },
    {
        "rule_id": "DET-PERIOD-001",
        "title": "履行期限不明确",
        "name": "履行期限明确性",
        "category": "履行期限",
        "severity": "medium",
        "logic": "未提取到起止时间或交付期限",
        "recommendation": "增加生效时间、履行期限、交付节点、验收时间和延期机制。",
    },
    {
        "rule_id": "DET-PAYMENT-001",
        "title": "付款条款缺失或不清晰",
        "name": "付款节点完整性",
        "category": "付款结算",
        "severity": "medium",
        "logic": "未提取到付款、发票或结算节点",
        "recommendation": "补充付款比例、时间、账户、发票类型、前置条件和逾期处理。",
    },
    {
        "rule_id": "DET-LIABILITY-001",
        "title": "缺少明确违约责任",
        "name": "违约责任完整性",
        "category": "违约责任",
        "severity": "high",
        "logic": "未提取到违约责任条款",
        "recommendation": "明确逾期交付、付款、质量、保密等责任承担方式。",
    },
    {
        "rule_id": "DET-LIABILITY-002",
        "title": "违约责任量化不足",
        "name": "违约责任可计算性",
        "category": "违约责任",
        "severity": "medium",
        "logic": "责任条款缺少比例、每日标准或计算方式",
        "recommendation": "增加违约金计算标准及补充赔偿机制。",
    },
    {
        "rule_id": "DET-DISPUTE-001",
        "title": "缺少争议解决条款",
        "name": "争议解决完整性",
        "category": "争议解决",
        "severity": "medium",
        "logic": "未提取到争议解决条款",
        "recommendation": "明确协商、诉讼或仲裁方式和管辖机构。",
    },
    {
        "rule_id": "DET-CONFIDENTIALITY-001",
        "title": "保密条款表达不充分",
        "name": "保密义务完整性",
        "category": "保密义务",
        "severity": "low",
        "logic": "出现保密表述但未提取到完整保密条款",
        "recommendation": "补充保密范围、期限、例外、返还销毁及违约责任。",
    },
    {
        "rule_id": "DET-TERMINATION-001",
        "title": "解除或终止机制不明确",
        "name": "退出机制完整性",
        "category": "解除终止",
        "severity": "low",
        "logic": "未提取到解除、终止或不可抗力机制",
        "recommendation": "增加解除条件、通知期限、终止结算和资料返还条款。",
    },
)

LEVEL_TO_CN = {"low": "低", "medium": "中", "high": "高", "critical": "严重"}


def _catalog() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": rule.rule_id,
            "title": rule.rule_name,
            "name": rule.rule_name,
            "category": rule.category,
            "severity": rule.severity.value,
            "logic": (
                f"{rule.condition_type.value}: "
                f"{', '.join(str(item) for item in rule.condition.get('patterns', []))}"
            ),
            "recommendation": rule.recommendation,
            "description": rule.description,
            "contract_type": rule.contract_type,
        }
        for rule in default_registry()
    ]


class RuleCenterError(ValueError):
    pass


class RuleCenterService:
    _lock = threading.Lock()

    def __init__(self, data_dir: Path, feedback_data_dir: Path | None = None) -> None:
        self.store = JsonDocumentStore(data_dir / "overrides.json", "rule_center_overrides")
        self.feedback_data_dir = feedback_data_dir

    def _overrides(self) -> dict[str, dict[str, Any]]:
        data = self.store.read({})
        return data if isinstance(data, dict) else {}

    def list_rules(self) -> list[RuleRecord]:
        overrides = self._overrides()
        feedback_by_rule = (
            RiskFeedbackService(self.feedback_data_dir).statistics().by_rule
            if self.feedback_data_dir
            else {}
        )
        now = datetime.now(timezone.utc)
        records: list[RuleRecord] = []
        for base in _catalog():
            override = overrides.get(base["rule_id"], {})
            severity = override.get("severity", base["severity"])
            feedback = feedback_by_rule.get(base["rule_id"], {})
            records.append(
                RuleRecord(
                    rule_id=base["rule_id"],
                    name=override.get("display_name", base["name"]),
                    category=base["category"],
                    contract_types=override.get("contract_types", [base["contract_type"]]),
                    severity=severity,
                    detection_method="deterministic_rule",
                    enabled=override.get("enabled", True),
                    version=int(override.get("version", 1)),
                    description=override.get("business_description", base["description"]),
                    match_logic_summary=base["logic"],
                    exclusion_logic_summary="仅在结构化提取满足对应缺失或不足条件时命中。",
                    recommendation=override.get("recommendation", base["recommendation"]),
                    test_samples=[base["title"]],
                    hit_count=None,
                    confirmed_count=feedback.get("confirmed"),
                    rejected_count=feedback.get("rejected"),
                    confirmation_rate=feedback.get("confirmation_rate"),
                    updated_at=datetime.fromisoformat(override["updated_at"])
                    if override.get("updated_at")
                    else now,
                )
            )
        return records

    def get(self, rule_id: str) -> RuleRecord:
        record = next((item for item in self.list_rules() if item.rule_id == rule_id), None)
        if record is None:
            raise RuleCenterError("规则不存在")
        return record

    def update(self, rule_id: str, payload: RuleUpdate) -> RuleRecord:
        self.get(rule_id)
        with self._lock:
            overrides = self._overrides()
            current = overrides.get(rule_id, {})
            changes = payload.model_dump(exclude_unset=True)
            if changes:
                current.update(changes)
                current["version"] = int(current.get("version", 1)) + 1
                current["updated_at"] = datetime.now(timezone.utc).isoformat()
                overrides[rule_id] = current
                self.store.write(overrides)
        return self.get(rule_id)

    def configured_registry(self, contract_type: str) -> list[RuleDefinition]:
        configured = {item.rule_id: item for item in self.list_rules()}
        result: list[RuleDefinition] = []
        for definition in default_registry():
            record = configured[definition.rule_id]
            applies = "all" in record.contract_types or contract_type in record.contract_types
            result.append(
                definition.model_copy(
                    update={
                        "rule_name": record.name,
                        "severity": Severity(record.severity),
                        "enabled": record.enabled and applies,
                        "recommendation": record.recommendation,
                    }
                )
            )
        return result

    def apply_to_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_title = {item["title"]: item for item in _catalog()}
        configured = {item.rule_id: item for item in self.list_rules()}
        result: list[dict[str, Any]] = []
        for finding in findings:
            base = by_title.get(str(finding.get("风险标题", "")))
            if base is None:
                result.append(finding)
                continue
            rule = configured[base["rule_id"]]
            if not rule.enabled:
                continue
            updated = dict(finding)
            updated["规则编号"] = rule.rule_id
            updated["风险等级"] = LEVEL_TO_CN[rule.severity]
            updated["修改方向"] = rule.recommendation
            updated["检测方式"] = "deterministic_rule"
            result.append(updated)
        for index, finding in enumerate(result, start=1):
            if finding.get("来源") == "规则审查":
                finding["风险编号"] = f"R{index:03d}"
        return result
