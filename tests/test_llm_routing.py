from contract_review.llm.routing import route_model_config


def test_deepseek_v4_pro_routes_fast_and_quality_roles() -> None:
    base = {
        "provider": "deepseek",
        "model_name": "deepseek-v4-pro",
        "api_key": "test-key-not-secret",
        "temperature": 0.1,
    }

    extraction = route_model_config(
        base,
        role="extraction",
        default_provider="openai",
        default_model_name="gpt-test",
    )
    compliance = route_model_config(
        base,
        role="compliance",
        default_provider="openai",
        default_model_name="gpt-test",
    )
    refinement = route_model_config(
        base,
        role="refinement",
        default_provider="openai",
        default_model_name="gpt-test",
    )

    assert extraction is not None
    assert compliance is not None
    assert refinement is not None
    assert extraction["model_name"] == "deepseek-v4-flash"
    assert compliance["model_name"] == "deepseek-v4-pro"
    assert refinement["model_name"] == "deepseek-v4-flash"
    assert base["model_name"] == "deepseek-v4-pro"


def test_routing_uses_environment_defaults_when_runtime_config_is_empty() -> None:
    routed = route_model_config(
        None,
        role="extraction",
        default_provider="deepseek",
        default_model_name="deepseek-v4-pro",
    )

    assert routed == {
        "provider": "deepseek",
        "model_name": "deepseek-v4-flash",
    }


def test_non_pro_or_non_deepseek_config_is_not_overridden() -> None:
    flash = {"provider": "deepseek", "model_name": "deepseek-v4-flash"}
    openai = {"provider": "openai", "model_name": "gpt-test"}

    assert route_model_config(
        flash,
        role="compliance",
        default_provider="deepseek",
        default_model_name="deepseek-v4-pro",
    ) == flash
    assert route_model_config(
        openai,
        role="extraction",
        default_provider="deepseek",
        default_model_name="deepseek-v4-pro",
    ) == openai
