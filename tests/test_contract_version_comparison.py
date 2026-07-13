from contract_review.services.version_comparison_service import VersionComparisonService


def test_version_comparison_preserves_history_and_maps_resolved_risk() -> None:
    result = VersionComparisonService().compare(
        from_version_id="version_1",
        to_version_id="version_2",
        old_text="第一条 付款周期为200天。\n第二条 乙方承担无限责任。",
        new_text="第一条 付款周期为30天。\n第二条 双方责任以合同金额为上限。",
        old_risks=[
            {
                "risk_id": "risk_payment",
                "contract_text": "付款周期为200天",
            },
            {
                "risk_id": "risk_liability",
                "contract_text": "乙方承担无限责任",
            },
        ],
    )
    operations = {item.operation for item in result.clause_diffs}
    assert {"added", "deleted"}.issubset(operations)
    assert all(item.status == "resolved" for item in result.risk_mappings)


def test_unchanged_risk_remains_unresolved() -> None:
    result = VersionComparisonService().compare(
        from_version_id="version_1",
        to_version_id="version_2",
        old_text="乙方承担无限责任。",
        new_text="乙方承担无限责任。\n新增交付说明。",
        old_risks=[{"risk_id": "risk_1", "contract_text": "乙方承担无限责任"}],
    )
    assert result.risk_mappings[0].status == "unresolved"
