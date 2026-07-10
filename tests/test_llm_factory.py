from contract_review.core.config import Settings
from contract_review.llm import factory


def test_claude_uses_native_anthropic_client(monkeypatch) -> None:
    captured = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(factory, "ChatAnthropic", FakeAnthropic)
    model = factory.create_chat_model(
        Settings(enable_llm=True),
        {
            "provider": "claude",
            "api_key": "sk-ant-test-value",
            "base_url": "https://api.anthropic.com/v1",
            "model_name": "claude-sonnet-4-5",
            "temperature": 0.2,
            "max_tokens": 2048,
        },
    )
    assert isinstance(model, FakeAnthropic)
    assert captured["api_key"] == "sk-ant-test-value"
    assert captured["base_url"] == "https://api.anthropic.com"
    assert captured["model"] == "claude-sonnet-4-5"


def test_deepseek_uses_openai_compatible_client(monkeypatch) -> None:
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(factory, "ChatOpenAI", FakeOpenAI)
    model = factory.create_chat_model(
        Settings(enable_llm=True),
        {
            "provider": "deepseek",
            "api_key": "sk-deepseek-value",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
        },
    )
    assert isinstance(model, FakeOpenAI)
    assert captured["base_url"] == "https://api.deepseek.com/v1"
