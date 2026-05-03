import pytest

from squire import providers
from squire.providers import (
    OpenAICompatibleProvider,
    Provider,
    REGISTRY,
    get_provider,
    register_provider,
)


@pytest.fixture(autouse=True)
def _restore_registry():
    """Snapshot and restore the provider registry around each test."""
    snapshot = dict(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)


def test_registry_includes_openai_compatible_by_default():
    assert "openai_compatible" in REGISTRY
    assert REGISTRY["openai_compatible"] is OpenAICompatibleProvider


def test_register_provider_round_trips_a_subclass():
    class FakeProv(Provider):
        def __init__(self, role_cfg):
            self.role_cfg = role_cfg

        def chat(self, messages, *, model, temperature, max_tokens):
            return "hi"

    register_provider("fake", FakeProv)
    p = get_provider({"provider_kind": "fake", "model": "m"})
    assert isinstance(p, FakeProv)
    assert p.chat([], model="m", temperature=0, max_tokens=10) == "hi"


def test_register_provider_rejects_non_subclass():
    with pytest.raises(TypeError):
        register_provider("bogus", object)  # type: ignore[arg-type]


def test_get_provider_unknown_kind_lists_available():
    with pytest.raises(ValueError, match="Unknown provider_kind"):
        get_provider({"provider_kind": "does-not-exist"})


def test_get_provider_defaults_to_openai_compatible(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    p = get_provider({
        "model": "x",
        "base_url": "http://localhost:1",
        "api_key_env": "GROQ_API_KEY",
    })
    assert isinstance(p, OpenAICompatibleProvider)


def test_openai_compatible_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Missing API key env var"):
        OpenAICompatibleProvider({"api_key_env": "GROQ_API_KEY", "base_url": "http://x"})


def test_openai_compatible_uses_role_specific_api_key_env(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_KEY", "abc")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # Should not raise — uses MY_CUSTOM_KEY, not GROQ_API_KEY.
    p = OpenAICompatibleProvider({"api_key_env": "MY_CUSTOM_KEY", "base_url": "http://x"})
    assert p.role_cfg["api_key_env"] == "MY_CUSTOM_KEY"


def test_openai_compatible_chat_calls_client_with_expected_args(monkeypatch):
    """Verify chat() builds the right OpenAI request and returns the response text."""
    monkeypatch.setenv("GROQ_API_KEY", "k")
    captured = {}

    class FakeChoice:
        def __init__(self, content):
            self.message = type("M", (), {"content": content})()

    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse("response text")

    class FakeClient:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            self.chat = type("C", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("openai.OpenAI", FakeClient)

    p = OpenAICompatibleProvider({
        "api_key_env": "GROQ_API_KEY",
        "base_url": "http://localhost:1",
    })
    out = p.chat(
        [{"role": "user", "content": "hello"}],
        model="m1",
        temperature=0.3,
        max_tokens=200,
    )
    assert out == "response text"
    assert captured["model"] == "m1"
    assert captured["temperature"] == 0.3
    assert captured["max_completion_tokens"] == 200
    assert captured["messages"] == [{"role": "user", "content": "hello"}]
