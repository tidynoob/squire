import json

from squire.session import _message_text, extract_session


def test_extract_session_keeps_only_user_assistant(session_jsonl, tmp_path):
    out = tmp_path / "clean.md"
    extract_session(session_jsonl, out)
    text = out.read_text()

    assert "## User" in text
    assert "Please fix X" in text
    assert "## Assistant" in text
    assert "I fixed X" in text
    assert "secret system prompt" not in text
    assert "very long tool output" not in text


def test_extract_session_truncates_long_messages(tmp_path):
    src = tmp_path / "session.jsonl"
    out = tmp_path / "out.md"
    src.write_text(json.dumps({"role": "user", "content": "x" * 20000}))
    extract_session(src, out, max_message_chars=100)

    text = out.read_text()
    assert "[TRUNCATED BY extract-session]" in text
    assert text.count("x") <= 200  # 100 kept + maybe the marker has none


def test_extract_session_skips_unparseable_lines(tmp_path):
    src = tmp_path / "session.jsonl"
    out = tmp_path / "out.md"
    src.write_text(
        json.dumps({"role": "user", "content": "real message"}) + "\n"
        + "{not valid json\n"
        + "\n"
        + json.dumps({"role": "assistant", "content": "real reply"}) + "\n"
    )
    extract_session(src, out)
    text = out.read_text()
    assert "real message" in text
    assert "real reply" in text


def test_extract_session_handles_list_content():
    obj = {"role": "user", "content": [{"text": "first"}, {"content": "second"}, "third"]}
    role, text = _message_text(obj)
    assert role == "user"
    assert "first" in text and "second" in text and "third" in text


def test_extract_session_returns_none_for_blank_or_missing_content():
    assert _message_text({"role": "user", "content": ""}) == (None, None)
    assert _message_text({"role": "user"}) == (None, None)
    assert _message_text({"role": "system", "content": "x"}) == (None, None)
