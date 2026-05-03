import json

from squire import metrics


def test_estimate_tokens_uses_4_chars_per_token():
    assert metrics.estimate_tokens(0) == 0
    assert metrics.estimate_tokens(4) == 1
    assert metrics.estimate_tokens(10) == 2  # round(10/4) -> 2 (banker's rounding)


def test_estimate_savings_matches_legacy_numbers():
    # These exact numbers are what the original worker_tools.py produced;
    # the test pins them so a refactor can't silently change the math.
    result = metrics.estimate_savings(input_chars=30233, output_chars=988, overhead_tokens=100)
    assert result["estimated_input_tokens"] == 7558
    assert result["estimated_main_tokens_with_worker"] == 347
    assert result["estimated_tokens_saved"] == 7211
    assert result["compression_ratio"] > 20


def test_estimate_savings_handles_zero_input():
    result = metrics.estimate_savings(0, 0)
    assert result["estimated_tokens_saved"] == 0
    assert result["estimated_percent_saved"] == 0
    assert result["compression_ratio"] == 0


def test_estimate_savings_clamps_negative_savings_to_zero():
    # If output is bigger than input, we didn't save anything — don't go negative.
    result = metrics.estimate_savings(input_chars=100, output_chars=10000)
    assert result["estimated_tokens_saved"] == 0


def test_log_event_appends_json_line_with_timestamp(tmp_path):
    log_path = tmp_path / "out.jsonl"
    cfg = {"monitoring": {"log_path": str(log_path)}}
    metrics.log_event({"role": "reader", "model": "m", "estimated_tokens_saved": 5}, cfg)
    metrics.log_event({"role": "writer", "model": "m", "estimated_tokens_saved": 7}, cfg)

    lines = log_path.read_text().splitlines()
    assert len(lines) == 2
    a, b = json.loads(lines[0]), json.loads(lines[1])
    assert a["role"] == "reader" and b["role"] == "writer"
    assert "ts" in a and "ts" in b
    # ISO-8601 with timezone
    assert "T" in a["ts"] and ("+" in a["ts"] or "Z" in a["ts"])
