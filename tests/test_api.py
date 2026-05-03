"""Direct kwargs invocations of the library API + import-smoke for the public surface."""
from __future__ import annotations

import importlib
import pathlib

import pytest

import squire
from squire import api, providers


@pytest.fixture(autouse=True)
def _restore_registry():
    snapshot = dict(providers.REGISTRY)
    yield
    providers.REGISTRY.clear()
    providers.REGISTRY.update(snapshot)


def _cfg(log_path):
    role = {
        "provider": "fake",
        "provider_kind": "fake",
        "model": "fake-model",
        "max_output_tokens": 500,
        "temperature": 0,
        "max_input_chars": 30000,
        "system_prompt": "be precise",
        "target_policy": "tmp_by_default",
    }
    return {
        "reader": role,
        "writer": role,
        "monitoring": {"log_path": str(log_path)},
    }


def test_public_api_exports_resolve_to_callables():
    """Every name in squire.__all__ must import and be callable (or a known constant)."""
    expected = {
        "ask", "write_artifact", "extract_session", "call_worker",
        "estimate_savings", "estimate_tokens", "load_config",
        "log_event", "write_default_config", "DEFAULT_CONFIG",
    }
    for name in expected:
        obj = getattr(squire, name)
        if name == "DEFAULT_CONFIG":
            assert isinstance(obj, dict)
        else:
            assert callable(obj), f"squire.{name} is not callable"


def test_ask_passes_question_and_returns_text_and_metrics(
    fake_provider_factory, tmp_path, tmp_log_path
):
    providers.register_provider("fake", fake_provider_factory(text="the answer"))
    f = tmp_path / "code.py"
    f.write_text("def hello(): pass")
    cfg = _cfg(tmp_log_path)

    text, metrics = api.ask([f], "what does it do?", cfg=cfg)

    assert text == "the answer"
    assert metrics["role"] == "reader"
    assert metrics["paths"] == [str(f)]
    assert metrics["input_chars"] > 0


def test_ask_respects_max_input_chars_override(fake_provider_factory, tmp_path, tmp_log_path):
    records: list = []
    providers.register_provider("fake", fake_provider_factory(text="ok", record=records))
    big = tmp_path / "big.py"
    big.write_text("x" * 5000)
    cfg = _cfg(tmp_log_path)

    api.ask([big], "q", cfg=cfg, max_input_chars=100)

    # Only ~100 chars of file content should reach the model in the corpus.
    user_msg = records[0]["messages"][1]["content"]
    assert "TRUNCATED" in user_msg
    assert user_msg.count("x") <= 200  # 100 from file + maybe some from path


def test_write_artifact_writes_to_tmp_by_default(
    fake_provider_factory, tmp_path, tmp_log_path
):
    providers.register_provider("fake", fake_provider_factory(text="generated content"))
    cfg = _cfg(tmp_log_path)
    target_request = pathlib.Path("/Users/someone/project/output.py")  # would be real path

    actual, metrics = api.write_artifact("spec for X", target_request, cfg=cfg)

    # Should have been redirected to /tmp/squire-worker/
    assert str(actual).startswith("/tmp/squire-worker/")
    assert actual.name == "output.py"
    assert actual.read_text() == "generated content"
    assert metrics["target"] == str(actual)
    assert metrics["context_paths"] == []


def test_write_artifact_allows_real_target_when_opted_in(
    fake_provider_factory, tmp_path, tmp_log_path
):
    providers.register_provider("fake", fake_provider_factory(text="real output"))
    cfg = _cfg(tmp_log_path)
    target = tmp_path / "real" / "out.py"

    actual, _ = api.write_artifact("spec", target, cfg=cfg, allow_real_target=True)

    assert actual == target
    assert target.read_text() == "real output"


def test_write_artifact_includes_context_files(
    fake_provider_factory, tmp_path, tmp_log_path
):
    records: list = []
    providers.register_provider("fake", fake_provider_factory(text="ok", record=records))
    cfg = _cfg(tmp_log_path)
    ctx = tmp_path / "ctx.py"
    ctx.write_text("CONTEXT_TOKEN_ABC")

    actual, metrics = api.write_artifact("spec", tmp_path / "out.py", context=[ctx], cfg=cfg)

    user_msg = records[0]["messages"][1]["content"]
    assert "CONTEXT_TOKEN_ABC" in user_msg
    assert metrics["context_paths"] == [str(ctx)]
