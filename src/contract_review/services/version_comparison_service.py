from __future__ import annotations

from difflib import SequenceMatcher

from contract_review.schemas.contract_management import (
    ClauseDiff,
    RiskRemediationMapping,
    VersionComparison,
)


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
        old_clauses = self._clauses(old_text)
        new_clauses = self._clauses(new_text)
        matcher = SequenceMatcher(a=old_clauses, b=new_clauses, autojunk=False)
        diffs: list[ClauseDiff] = []
        for operation, old_start, old_end, new_start, new_end in matcher.get_opcodes():
            if operation == "equal":
                diffs.extend(ClauseDiff(operation="unchanged", text=value) for value in old_clauses[old_start:old_end])
            elif operation == "delete":
                diffs.extend(ClauseDiff(operation="deleted", text=value) for value in old_clauses[old_start:old_end])
            elif operation == "insert":
                diffs.extend(ClauseDiff(operation="added", text=value) for value in new_clauses[new_start:new_end])
            else:
                diffs.extend(ClauseDiff(operation="deleted", text=value) for value in old_clauses[old_start:old_end])
                diffs.extend(ClauseDiff(operation="added", text=value) for value in new_clauses[new_start:new_end])
        mappings = [self._map_risk(risk, new_text) for risk in old_risks or []]
        return VersionComparison(
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            clause_diffs=diffs,
            risk_mappings=mappings,
        )

    def _map_risk(self, risk: dict[str, str], new_text: str) -> RiskRemediationMapping:
        old_clause = risk.get("contract_text", "").strip()
        risk_id = risk.get("risk_id", "unknown")
        if old_clause and old_clause in new_text:
            status = "unresolved"
            new_clause = old_clause
        elif old_clause and any(segment in new_text for segment in self._tokens(old_clause)):
            status = "partially_resolved"
            new_clause = next((segment for segment in self._tokens(old_clause) if segment in new_text), None)
        else:
            status = "resolved"
            new_clause = None
        return RiskRemediationMapping(
            risk_id=risk_id,
            status=status,
            old_text=old_clause,
            new_text=new_clause,
        )

    def _clauses(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _tokens(self, text: str) -> list[str]:
        return [token for token in text.replace("。", " ").replace("，", " ").split() if len(token) >= 4]
