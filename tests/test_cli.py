"""All four CLIs invoked via main(argv) with monkey-patched provider — same flags as today."""
from __future__ import annotations

import io
import json
import pathlib

import pytest

from squire import cli, providers


@pytest.fixture(autouse=True)
def _restore_registry():
    snapshot = dict(providers.REGISTRY)
    yield
    providers.REGISTRY.clear()
    providers.REGISTRY.update(snapshot)


@pytest.fixture
def fake_cfg(tmp_path, monkeypatch, fake_provider_factory):
    """Set up an isolated config file pointing at a fake provider + tmp log."""
    import yaml

    cfg_file = tmp_path / "config.yaml"
    log_file = tmp_path / "delegation.jsonl"
    cfg_file.write_text(yaml.safe_dump({
        "reader": {
            "provider": "fake",
            "provider_kind": "fake",
            "model": "fake-model",
            "max_output_tokens": 500,
            "temperature": 0,
            "max_input_chars": 30000,
            "system_prompt": "be precise",
        },
        "writer": {
            "provider": "fake",
            "provider_kind": "fake",
            "model": "fake-model",
            "max_output_tokens": 500,
            "temperature": 0,
            "max_input_chars": 30000,
            "system_prompt": "be careful",
            "target_policy": "tmp_by_default",
        },
        "monitoring": {"log_path": str(log_file), "print_metrics": False},
    }))
    monkeypatch.setenv("SQUIRE_CONFIG", str(cfg_file))
    return {"cfg_file": cfg_file, "log_file": log_file}


def test_ask_main_prints_text_and_exits_zero(
    fake_cfg, fake_provider_factory, tmp_path, capsys
):
    providers.register_provider("fake", fake_provider_factory(text="answer text"))
    f = tmp_path / "code.py"
    f.write_text("def x(): pass")

    rc = cli.ask_main(["--paths", str(f), "--question", "what is x"])

    assert rc == 0
    captured = capsys.readouterr()
    assert "answer text" in captured.out
    # No metrics by default (config sets print_metrics: false, no --metrics flag).
    assert "worker metrics" not in captured.err


def test_ask_main_metrics_flag_prints_metrics_to_stderr(
    fake_cfg, fake_provider_factory, tmp_path, capsys
):
    providers.register_provider("fake", fake_provider_factory(text="answer"))
    f = tmp_path / "x.py"
    f.write_text("data")

    cli.ask_main(["--paths", str(f), "--question", "q", "--metrics"])

    captured = capsys.readouterr()
    assert "worker metrics" in captured.err
    assert '"role": "reader"' in captured.err
    assert '"model": "fake-model"' in captured.err


def test_write_main_redirects_to_tmp_by_default(
    fake_cfg, fake_provider_factory, tmp_path, capsys
):
    providers.register_provider("fake", fake_provider_factory(text="generated"))

    rc = cli.write_main(["--spec", "make a thing", "--target", "/Users/x/proj/out.py"])
    assert rc == 0
    captured = capsys.readouterr()
    actual = captured.out.strip()
    assert actual.startswith("/tmp/squire-worker/")
    assert pathlib.Path(actual).read_text() == "generated"


def test_write_main_allow_real_target_writes_literal_path(
    fake_cfg, fake_provider_factory, tmp_path, capsys
):
    providers.register_provider("fake", fake_provider_factory(text="real"))
    target = tmp_path / "out.txt"

    cli.write_main(["--spec", "x", "--target", str(target), "--allow-real-target"])

    assert target.read_text() == "real"


def test_extract_main_writes_markdown(session_jsonl, tmp_path, capsys):
    out = tmp_path / "clean.md"
    rc = cli.extract_main([str(session_jsonl), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    text = out.read_text()
    assert "## User" in text and "## Assistant" in text


def test_stats_main_with_no_log_says_so(monkeypatch, tmp_path, capsys):
    import yaml
    cfg_file = tmp_path / "cfg.yaml"
    log_file = tmp_path / "missing.jsonl"
    cfg_file.write_text(yaml.safe_dump({"monitoring": {"log_path": str(log_file)}}))
    monkeypatch.setenv("SQUIRE_CONFIG", str(cfg_file))

    rc = cli.stats_main([])

    assert rc == 0
    assert "No worker log yet." in capsys.readouterr().out


def test_stats_main_aggregates_log(monkeypatch, tmp_path, capsys):
    import yaml
    cfg_file = tmp_path / "cfg.yaml"
    log_file = tmp_path / "events.jsonl"
    cfg_file.write_text(yaml.safe_dump({"monitoring": {"log_path": str(log_file)}}))
    log_file.write_text(
        json.dumps({"role": "reader", "model": "m", "estimated_input_tokens": 1000, "estimated_main_tokens_with_worker": 100, "estimated_tokens_saved": 900}) + "\n"
        + json.dumps({"role": "writer", "model": "m", "estimated_input_tokens": 500, "estimated_main_tokens_with_worker": 80, "estimated_tokens_saved": 420}) + "\n"
    )
    monkeypatch.setenv("SQUIRE_CONFIG", str(cfg_file))

    cli.stats_main([])

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["events"] == 2
    assert parsed["estimated_main_tokens_saved"] == 1320
    assert parsed["saved_by_role"] == {"reader": 900, "writer": 420}


def test_init_config_main_creates_file(tmp_path, capsys):
    target = tmp_path / "new_config.yaml"
    rc = cli.init_config_main(["--path", str(target)])
    assert rc == 0
    assert target.exists()
    assert capsys.readouterr().out.strip() == str(target)


def test_dispatcher_routes_known_commands(fake_cfg, fake_provider_factory, tmp_path, capsys):
    providers.register_provider("fake", fake_provider_factory(text="dispatched"))
    f = tmp_path / "x.py"
    f.write_text("data")
    rc = cli.dispatcher_main(["ask", "--paths", str(f), "--question", "q"])
    assert rc == 0
    assert "dispatched" in capsys.readouterr().out


def test_dispatcher_unknown_command_returns_2(capsys):
    rc = cli.dispatcher_main(["nosuch"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown command" in err


def test_dispatcher_help_returns_zero(capsys):
    rc = cli.dispatcher_main(["--help"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Commands:" in out
