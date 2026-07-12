from contract_review.rules.models import Severity

SEVERITY_WEIGHT = {
    Severity.low: 25.0,
    Severity.medium: 50.0,
    Severity.high: 75.0,
    Severity.critical: 95.0,
}


def deterministic_risk_score(severity: Severity, *, evidence_reliability: float = 1.0) -> float:
    """Stable, public formula: severity base x deterministic evidence reliability."""
    reliability = min(1.0, max(0.0, evidence_reliability))
    return round(SEVERITY_WEIGHT[severity] * (0.8 + 0.2 * reliability), 2)
