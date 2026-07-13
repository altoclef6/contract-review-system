from scripts.benchmark_ablation import benchmark


def test_ablation_benchmark_does_not_fabricate_live_metrics() -> None:
    result = benchmark()
    assert set(result) >= {
        "A_single_prompt",
        "B_rules_plus_single_prompt",
        "C_multi_agent",
        "D_multi_agent_rag_rules",
    }
    assert result["B_rules_plus_single_prompt"]["status"] == "deterministic benchmark"
    assert result["A_single_prompt"]["f1"] == "未进行真实测量"
    assert result["D_multi_agent_rag_rules"]["cost"] == "未进行真实测量"
