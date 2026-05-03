import json

import pytest

from squire import client, providers


@pytest.fixture(autouse=True)
def _restore_registry():
    snapshot = dict(providers.REGISTRY)
    yield
    providers.REGISTRY.clear()
    providers.REGISTRY.update(snapshot)


def _cfg(log_path, *, response_text="answer", role_overrides=None):
    role = {
        "provider": "fake",
        "provider_kind": "fake",
        "model": "fake-model",
        "max_output_tokens": 500,
        "temperature": 0,
        "system_prompt": "be precise",
    }
    if role_overrides:
        role.update(role_overrides)
    return {
        "reader": role,
        "writer": role,
        "monitoring": {"log_path": str(log_path)},
    }, response_text


def test_strip_reasoning_tags_removes_think_blocks():
    raw = "<think>internal monologue</think>actual answer"
    assert client.strip_reasoning_tags(raw) == "actual answer"


def test_strip_reasoning_tags_handles_multiline_and_case():
    raw = "<THINK>\nlong\nthought\n</think>\n\nfinal"
    assert client.strip_reasoning_tags(raw) == "final"


def test_strip_reasoning_tags_passes_through_clean_text():
    assert client.strip_reasoning_tags("plain answer") == "plain answer"
    assert client.strip_reasoning_tags("") == ""
    assert client.strip_reasoning_tags(None) == ""  # type: ignore[arg-type]


def test_call_worker_sends_corpus_and_question_to_provider(fake_provider_factory, tmp_log_path):
    records: list = []
    providers.register_provider("fake", fake_provider_factory(text="result", record=records))
    cfg, _ = _cfg(tmp_log_path)

    text, metrics = client.call_worker("reader", "FILE CONTENT", "the question", cfg)

    assert text == "result"
    assert len(records) == 1
    msgs = records[0]["messages"]
    assert msgs[0] == {"role": "system", "content": "be precise"}
    assert "FILE CONTENT" in msgs[1]["content"]
    assert msgs[2]["content"] == "the question"
    assert records[0]["model"] == "fake-model"
    assert records[0]["max_tokens"] == 500


def test_call_worker_strips_reasoning_tags_from_response(fake_provider_factory, tmp_log_path):
    providers.register_provider("fake", fake_provider_factory(text="<think>x</think>clean"))
    cfg, _ = _cfg(tmp_log_path)

    text, _ = client.call_worker("reader", "c", "q", cfg)

    assert text == "clean"


def test_call_worker_metrics_have_expected_shape(fake_provider_factory, tmp_log_path):
    providers.register_provider("fake", fake_provider_factory(text="abc"))
    cfg, _ = _cfg(tmp_log_path)

    _, metrics = client.call_worker("reader", "x" * 100, "q", cfg)

    for key in (
        "role", "provider", "model", "latency_sec", "input_chars", "output_chars",
        "estimated_input_tokens", "estimated_tokens_saved", "estimated_percent_saved",
        "compression_ratio",
    ):
        assert key in metrics, f"missing metric: {key}"
    assert metrics["role"] == "reader"
    assert metrics["model"] == "fake-model"


def test_call_worker_logs_event_to_jsonl(fake_provider_factory, tmp_log_path):
    providers.register_provider("fake", fake_provider_factory(text="abc"))
    cfg, _ = _cfg(tmp_log_path)

    client.call_worker("reader", "corpus", "question", cfg)

    lines = tmp_log_path.read_text().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "reader"
    assert event["role"] == "reader"
    assert event["model"] == "fake-model"
    assert "ts" in event
