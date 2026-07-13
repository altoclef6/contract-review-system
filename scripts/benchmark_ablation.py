from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from contract_review.rules import RuleEngine, default_registry

ROOT = Path(__file__).resolve().parents[1]


def benchmark() -> dict[str, object]:
    texts = [
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "samples" / "generated").glob("*.txt"))
        if path.stat().st_size
    ]
    started = perf_counter()
    engine = RuleEngine(default_registry())
    findings = [engine.evaluate(text, "software_development") for text in texts]
    duration_ms = (perf_counter() - started) * 1000
    deterministic = {
        "status": "deterministic benchmark",
        "sample_count": len(texts),
        "finding_count": sum(len(items) for items in findings),
        "average_duration_ms": round(duration_ms / len(texts), 3) if texts else None,
        "precision": "see scripts/evaluate_review.py partial-label benchmark",
        "recall": "see scripts/evaluate_review.py partial-label benchmark",
        "f1": "see scripts/evaluate_review.py partial-label benchmark",
        "tokens": 0,
        "cost": 0,
        "legal_basis_traceability": "未进行真实测量",
        "text_location_rate": round(
            sum(item.start_offset is not None for items in findings for item in items)
            / max(1, sum(len(items) for items in findings)),
            4,
        ),
    }
    unavailable = {
        "status": "mocked integration structure only",
        "precision": "未进行真实测量",
        "recall": "未进行真实测量",
        "f1": "未进行真实测量",
        "average_duration_ms": "未进行真实测量",
        "tokens": "未进行真实测量",
        "cost": "未进行真实测量",
        "legal_basis_traceability": "未进行真实测量",
        "text_location_rate": "未进行真实测量",
    }
    return {
        "A_single_prompt": dict(unavailable),
        "B_rules_plus_single_prompt": deterministic,
        "C_multi_agent": dict(unavailable),
        "D_multi_agent_rag_rules": dict(unavailable),
        "disclaimer": "No live model benchmark was run. Mocked rows contain no fabricated model metrics.",
    }


if __name__ == "__main__":
    print(json.dumps(benchmark(), ensure_ascii=False, indent=2))
