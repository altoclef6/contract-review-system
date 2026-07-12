from __future__ import annotations

import re
from time import perf_counter

from contract_review.rules.models import ConditionType, RuleDefinition, RuleMatch
from contract_review.rules.scoring import deterministic_risk_score


class RuleEngine:
    def __init__(self, rules: list[RuleDefinition]) -> None:
        self.rules = rules

    def evaluate(self, text: str, contract_type: str) -> list[RuleMatch]:
        results: list[RuleMatch] = []
        seen: set[str] = set()
        for rule in self.rules:
            if not rule.enabled or rule.rule_id in seen:
                continue
            if rule.contract_type not in {"all", contract_type}:
                continue
            started = perf_counter()
            try:
                span = self._match(rule, text)
            except (re.error, TypeError, ValueError):
                continue
            if span is None:
                continue
            start, end = span
            excerpt = text[start:end] if end > start else ""
            results.append(
                RuleMatch(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    category=rule.category,
                    severity=rule.severity,
                    risk_score=deterministic_risk_score(rule.severity),
                    contract_text=excerpt,
                    normalized_text=" ".join(excerpt.split()),
                    paragraph_index=text[:start].count("\n") if excerpt else None,
                    start_offset=start if excerpt else None,
                    end_offset=end if excerpt else None,
                    explanation=rule.explanation,
                    legal_basis=rule.legal_basis_ids,
                    recommendation=rule.recommendation,
                    suggested_revision=rule.suggested_revision_template,
                    requires_human_review=rule.requires_human_review
                    or rule.severity.value in {"high", "critical"},
                    execution_ms=round((perf_counter() - started) * 1000, 3),
                )
            )
            seen.add(rule.rule_id)
        return results

    def _match(self, rule: RuleDefinition, text: str) -> tuple[int, int] | None:
        patterns = [str(value) for value in rule.condition.get("patterns", [])]
        if rule.condition_type == ConditionType.missing:
            return (0, 0) if not any(re.search(pattern, text, re.I) for pattern in patterns) else None
        if rule.condition_type in {ConditionType.regex, ConditionType.keyword}:
            for pattern in patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    return match.span()
        if rule.condition_type == ConditionType.all:
            matches = [re.search(pattern, text, re.I) for pattern in patterns]
            if matches and all(matches):
                present = [match for match in matches if match is not None]
                return min(match.start() for match in present), max(match.end() for match in present)
        if rule.condition_type == ConditionType.any:
            for pattern in patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    return match.span()
        return None
