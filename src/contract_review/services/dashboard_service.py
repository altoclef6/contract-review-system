from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from contract_review.schemas.auth import UserPublic, UserRole
from contract_review.schemas.dashboard import (
    DashboardDistributionItem,
    DashboardMetrics,
    DashboardRecentTask,
    DashboardRuleItem,
    DashboardSummary,
    DashboardTodoItem,
    DashboardTrendPoint,
)
from contract_review.services.history_service import HistoryService
from contract_review.services.workflow_service import WorkflowService

RISK_LABELS = {
    "critical": "严重风险", "high": "高风险", "medium": "中风险",
    "low": "低风险", "unknown": "未标注",
}
CONTRACT_TYPE_LABELS = {
    "general": "通用合同", "purchase": "采购合同", "sales": "销售合同",
    "employment": "劳动合同", "labor": "劳动合同", "lease": "租赁合同",
    "nda": "保密协议", "service": "服务合同", "software_development": "软件开发合同",
    "technical_service": "技术服务合同", "information_system": "信息系统建设合同",
    "software_outsourcing": "软件外包合同", "other": "其他合同",
}


class DashboardService:
    """Aggregate one history snapshot and one workflow snapshot using UTC boundaries."""

    def __init__(self, history: HistoryService, workflows: WorkflowService) -> None:
        self.history = history
        self.workflows = workflows

    def summary(self, actor: UserPublic, *, now: datetime | None = None) -> DashboardSummary:
        current = self._as_utc(now or datetime.now(timezone.utc))
        records = self._authorized_records(actor)
        workflows = self._authorized_workflows(actor)
        month_start = datetime.combine(current.date().replace(day=1), time.min, timezone.utc)
        next_month = (
            datetime(current.year + 1, 1, 1, tzinfo=timezone.utc)
            if current.month == 12
            else datetime(current.year, current.month + 1, 1, tzinfo=timezone.utc)
        )
        month_records = self._records_between(
            records,
            month_start,
            min(next_month, current + timedelta(microseconds=1)),
        )
        trend_start_date = current.date() - timedelta(days=29)
        trend_start = datetime.combine(trend_start_date, time.min, timezone.utc)
        trend_end = datetime.combine(current.date() + timedelta(days=1), time.min, timezone.utc)
        recent_period_records = self._records_between(records, trend_start, trend_end)
        durations = [
            float(item["duration_ms"])
            for item in month_records
            if self._is_non_negative_number(item.get("duration_ms"))
        ]
        high_risk_count = sum(
            1
            for item in month_records
            if self._risk_key(item.get("overall_risk_level")) in {"high", "critical"}
        )
        top_rules = self._top_rules(recent_period_records)
        unavailable = {
            "pending_human_review_risk_count": "当前风险复核状态尚未持久化，无法可靠计算待人工复核数量。",
            "failed_tasks": "当前历史服务只保存成功审查，失败任务尚无可靠持久化数据。",
            "rectifying_risks": "风险整改状态尚未持久化，暂不能形成整改待办。",
        }
        if top_rules is None:
            unavailable["top_risk_rules"] = "部分历史审查没有规则聚合快照；为避免逐份读取报告，暂不展示不完整排名。"
        return DashboardSummary(
            generated_at=current,
            scope="all" if actor.role is UserRole.admin else "owned",
            metrics=DashboardMetrics(
                monthly_review_count=len(month_records),
                monthly_high_risk_contract_count=high_risk_count,
                pending_human_review_risk_count=None,
                average_review_duration_ms=round(sum(durations) / len(durations), 2) if durations else None,
            ),
            review_trend_30d=self._trend(recent_period_records, trend_start_date),
            risk_level_distribution=self._risk_distribution(recent_period_records),
            contract_type_distribution=self._contract_type_distribution(recent_period_records),
            top_risk_rules=top_rules,
            recent_tasks=self._recent_tasks(records),
            todos=self._todos(workflows, actor),
            unavailable_reasons=unavailable,
            statistics_notes=[
                "所有日期边界和聚合时间均使用 UTC。",
                "本月指标仅统计已写入审查历史的完成记录。",
                "高风险合同当前按高/严重风险审查记录计数，合同与审查统一关联后再切换为合同去重口径。",
                "平均耗时仅使用 duration_ms 有效且非负的本月记录，分母为零时返回 null。",
                "当前历史仅保存成功审查；最近任务的开始时间由历史写入时间减去 duration_ms 推导。",
            ],
        )

    def _authorized_records(self, actor: UserPublic) -> list[dict[str, Any]]:
        records = self.history.list_records()
        if actor.role is UserRole.admin:
            return records
        return [item for item in records if item.get("created_by") == actor.id]

    def _authorized_workflows(self, actor: UserPublic) -> list[dict[str, Any]]:
        records = [item.model_dump(mode="json") for item in self.workflows.list_for_user(actor)]
        if actor.role is UserRole.admin:
            return records
        return [item for item in records if item.get("submitter_id") == actor.id]

    def _records_between(self, records: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for item in records:
            created_at = self._parse_datetime(item.get("created_at"))
            if created_at is not None and start <= created_at < end:
                selected.append(item)
        return selected

    def _trend(self, records: list[dict[str, Any]], start_date: date) -> list[DashboardTrendPoint]:
        counts: Counter[str] = Counter()
        for item in records:
            created_at = self._parse_datetime(item.get("created_at"))
            if created_at:
                counts[created_at.date().isoformat()] += 1
        return [
            DashboardTrendPoint(date=(start_date + timedelta(days=offset)).isoformat(), count=counts[(start_date + timedelta(days=offset)).isoformat()])
            for offset in range(30)
        ]

    def _risk_distribution(self, records: list[dict[str, Any]]) -> list[DashboardDistributionItem]:
        counts = Counter(self._risk_key(item.get("overall_risk_level")) for item in records)
        return [DashboardDistributionItem(key=key, label=RISK_LABELS[key], value=counts[key]) for key in ("critical", "high", "medium", "low", "unknown") if counts[key]]

    def _contract_type_distribution(self, records: list[dict[str, Any]]) -> list[DashboardDistributionItem]:
        counts = Counter(str(item.get("contract_type") or "general") for item in records)
        return [
            DashboardDistributionItem(key=key, label=CONTRACT_TYPE_LABELS.get(key, key), value=value)
            for key, value in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    def _top_rules(self, records: list[dict[str, Any]]) -> list[DashboardRuleItem] | None:
        if not records:
            return []
        if any(item.get("rule_counts_complete") is not True for item in records):
            return None
        counts: Counter[str] = Counter()
        titles: dict[str, str] = {}
        for item in records:
            for rule in item.get("rule_counts", []):
                rule_id, count = str(rule.get("rule_id") or "").strip(), rule.get("count")
                if not rule_id or not isinstance(count, int) or count < 1:
                    continue
                counts[rule_id] += count
                titles.setdefault(rule_id, str(rule.get("title") or rule_id))
        return [DashboardRuleItem(rule_id=rule_id, title=titles[rule_id], count=count) for rule_id, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:5]]

    def _recent_tasks(self, records: list[dict[str, Any]]) -> list[DashboardRecentTask]:
        sortable = [(created_at, item) for item in records if (created_at := self._parse_datetime(item.get("created_at"))) is not None]
        sortable.sort(key=lambda pair: pair[0], reverse=True)
        result: list[DashboardRecentTask] = []
        for completed_at, item in sortable[:8]:
            duration = item.get("duration_ms")
            valid_duration = (
                int(duration)
                if isinstance(duration, (int, float))
                and not isinstance(duration, bool)
                and duration >= 0
                else None
            )
            result.append(DashboardRecentTask(
                review_id=str(item.get("review_id")), contract_name=str(item.get("file_name") or "未命名合同"),
                contract_type=str(item.get("contract_type") or "general"), status="completed",
                risk_level=item.get("overall_risk_level"),
                started_at=completed_at - timedelta(milliseconds=valid_duration) if valid_duration is not None else None,
                duration_ms=valid_duration,
            ))
        return result

    def _todos(self, workflows: list[dict[str, Any]], actor: UserPublic) -> list[DashboardTodoItem]:
        result: list[DashboardTodoItem] = []
        for item in workflows:
            step = str(item.get("current_step"))
            definition: tuple[str, str] | None = None
            if step == "uploaded":
                definition = ("待启动 AI 初审", "合同已进入流程，尚未启动现有 AI 初审动作。")
            elif step == "legal_review" and actor.role in {UserRole.admin, UserRole.legal}:
                definition = ("待法务审核", "现有审批流程已进入法务审核节点。")
            elif step == "manager_review" and actor.role is UserRole.admin:
                definition = ("待主管审核", "现有审批流程已进入主管审核节点。")
            elif step == "rejected" and item.get("submitter_id") == actor.id:
                definition = ("待重新提交", "该流程已被驳回，可检查意见后重新提交。")
            updated_at = self._parse_datetime(item.get("updated_at"))
            if definition is None or updated_at is None:
                continue
            result.append(DashboardTodoItem(
                id=str(item.get("id")), source="workflow", title=definition[0],
                description=f"合同 {item.get('contract_id')}：{definition[1]}",
                status=str(item.get("status") or step), updated_at=updated_at, action_path="/workflows",
            ))
        result.sort(key=lambda item: item.updated_at, reverse=True)
        return result[:8]

    @staticmethod
    def _risk_key(value: Any) -> str:
        normalized = str(value or "").strip().casefold()
        if normalized in {"严重", "严重风险", "critical"}:
            return "critical"
        if normalized in {"高", "高风险", "high"}:
            return "high"
        if normalized in {"中", "中风险", "medium"}:
            return "medium"
        if normalized in {"低", "低风险", "low"}:
            return "low"
        return "unknown"

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return DashboardService._as_utc(value)
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return DashboardService._as_utc(parsed)
        except ValueError:
            return None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _is_non_negative_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
