import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_dataset_has_twenty_gold_labels() -> None:
    labels = sorted((ROOT / "samples" / "expected_results").glob("*.json"))
    fixtures = [
        path
        for path in (ROOT / "samples" / "generated").iterdir()
        if path.is_file() and path.name != "README.md"
    ]
    assert len(labels) == 20
    assert len(fixtures) == 20
    for label_path in labels:
        label = json.loads(label_path.read_text(encoding="utf-8"))
        assert label["fixture_type"] == "fully_fictional_test_data"
        assert "expected_risks" in label
        assert "should_not_match" in label


def test_security_fixtures_are_safe_and_small() -> None:
    generated = ROOT / "samples" / "generated"
    assert (generated / "16_disguised_executable.pdf").read_bytes().startswith(b"MZ")
    manifest = json.loads((generated / "18_oversize_manifest.json").read_text(encoding="utf-8"))
    assert manifest["materialize"] is False
    assert sum(path.stat().st_size for path in generated.iterdir() if path.is_file()) < 5_000_000
