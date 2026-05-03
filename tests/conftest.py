"""Shared fixtures: env isolation, fake provider, tmp config + log."""
from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any, Dict, List

import pytest

# Make `import squire` work without `pip install -e` for fast local dev.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Prevent tests from reading or writing the user's real ~/.hermes/.env or config."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_home"))
    monkeypatch.setenv("SQUIRE_HOME", str(tmp_path / "squire_home"))
    monkeypatch.delenv("SQUIRE_CONFIG", raising=False)
    monkeypatch.delenv("HERMES_WORKER_CONFIG", raising=False)
    yield


@pytest.fixture
def tmp_config_path(tmp_path, monkeypatch) -> pathlib.Path:
    """Provide an isolated config path and point load_config at it."""
    cfg = tmp_path / "squire_config.yaml"
    monkeypatch.setenv("SQUIRE_CONFIG", str(cfg))
    return cfg


@pytest.fixture
def tmp_log_path(tmp_path) -> pathlib.Path:
    """Provide an isolated JSONL log path."""
    return tmp_path / "delegation.jsonl"


@pytest.fixture
def fake_provider_factory():
    """Build a FakeProvider class that records calls and returns a canned response.

    Use ``register_provider("fake", factory(text="..."))`` in tests.
    """
    from squire.providers import Provider

    def _build(text: str = "fake response", record: List[Dict[str, Any]] | None = None):
        records = record if record is not None else []

        class FakeProvider(Provider):
            def __init__(self, role_cfg: Dict[str, Any]) -> None:
                self.role_cfg = role_cfg

            def chat(self, messages, *, model, temperature, max_tokens):
                records.append({
                    "messages": messages,
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                })
                return text

        FakeProvider.records = records
        return FakeProvider

    return _build


@pytest.fixture
def session_jsonl(tmp_path) -> pathlib.Path:
    """A small JSONL session with a mix of role types."""
    src = tmp_path / "session.jsonl"
    rows = [
        {"role": "system", "content": "secret system prompt"},
        {"role": "user", "content": "Please fix X"},
        {"role": "assistant", "content": "I fixed X"},
        {"type": "tool_call", "name": "read_file", "args": {"path": "big.py"}},
        {"role": "tool", "content": "very long tool output"},
    ]
    src.write_text("\n".join(json.dumps(r) for r in rows))
    return src
