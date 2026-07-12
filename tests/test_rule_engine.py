from contract_review.rules import RuleEngine, default_registry
from contract_review.rules.models import Severity
from contract_review.rules.scoring import deterministic_risk_score


def test_default_registry_contains_sixty_real_rules() -> None:
    rules = default_registry()
    assert len(rules) == 60
    assert len({rule.rule_id for rule in rules}) == 60
    assert all(rule.explanation and rule.recommendation for rule in rules)


def test_rule_results_are_deterministic_and_located() -> None:
    text = "第一条 项目范围包括但不限于甲方要求的其他工作。\n第二条 乙方承担无限责任，赔偿不设上限。"
    engine = RuleEngine(default_registry())
    first = engine.evaluate(text, "software_development")
    second = engine.evaluate(text, "software_development")
    first_core = [(item.rule_id, item.start_offset, item.end_offset, item.risk_score) for item in first]
    second_core = [(item.rule_id, item.start_offset, item.end_offset, item.risk_score) for item in second]
    assert first_core == second_core
    open_scope = next(item for item in first if item.rule_id == "R004")
    assert open_scope.contract_text
    assert text[open_scope.start_offset : open_scope.end_offset] == open_scope.contract_text


def test_missing_clause_and_high_risk_require_human_review() -> None:
    results = RuleEngine(default_registry()).evaluate("软件开发服务合同", "software_development")
    by_id = {item.rule_id: item for item in results}
    assert by_id["R008"].contract_text == ""
    assert by_id["R008"].requires_human_review is True
    assert by_id["R036"].source == "deterministic_rule"


def test_invalid_rule_does_not_abort_engine() -> None:
    rules = default_registry()
    rules[0].condition["patterns"] = ["["]
    results = RuleEngine(rules).evaluate("软件开发服务合同", "software_development")
    assert results
    assert all(item.rule_id != "R001" for item in results)


def test_public_score_formula_is_stable() -> None:
    assert deterministic_risk_score(Severity.high) == 75.0
    assert deterministic_risk_score(Severity.critical) == 95.0
