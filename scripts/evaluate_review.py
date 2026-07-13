from __future__ import annotations

import json
import statistics
from pathlib import Path
from time import perf_counter

from contract_review.rules import RuleEngine, default_registry

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    gold_dir = ROOT / "samples" / "expected_results"
    sample_dir = ROOT / "samples" / "generated"
    engine = RuleEngine(default_registry())
    true_positive = false_positive = false_negative = 0
    durations: list[float] = []
    evaluated = 0
    expected_total = actual_total = located = 0

    for gold_path in sorted(gold_dir.glob("*.json")):
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        sample_path = sample_dir / gold["file_name"]
        if sample_path.suffix != ".txt" or not sample_path.exists() or not sample_path.stat().st_size:
            continue
        text = sample_path.read_text(encoding="utf-8")
        started = perf_counter()
        matches = engine.evaluate(text, "software_development")
        durations.append((perf_counter() - started) * 1000)
        actual = {item.rule_id for item in matches}
        expected = {item["rule_id"] for item in gold["expected_risks"]}
        ignored = actual - expected - set(gold["should_not_match"])
        true_positive += len(actual & expected)
        false_negative += len(expected - actual)
        false_positive += len(ignored)
        expected_total += len(expected)
        actual_total += len(actual)
        located += sum(item.start_offset is not None for item in matches)
        evaluated += 1

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    ordered = sorted(durations)
    p95_index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))) if ordered else 0
    report = {
        "benchmark_type": "deterministic benchmark",
        "sample_count": evaluated,
        "expected_risk_count": expected_total,
        "actual_risk_count": actual_total,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "average_duration_ms": round(statistics.mean(durations), 3) if durations else None,
        "p50_duration_ms": round(statistics.median(durations), 3) if durations else None,
        "p95_duration_ms": round(ordered[p95_index], 3) if ordered else None,
        "average_input_tokens": "未进行真实测量",
        "average_output_tokens": "未进行真实测量",
        "average_cost": "未进行真实测量",
        "rule_engine_hit_rate": round(true_positive / expected_total, 4) if expected_total else 0,
        "legal_basis_traceability": "未进行真实测量",
        "text_location_rate": round(located / actual_total, 4) if actual_total else 0,
        "note": "Binary/OCR fixtures are integration fixtures and are excluded from this text-only deterministic benchmark.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
