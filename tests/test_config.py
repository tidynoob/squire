import os
import pathlib

import pytest
import yaml

from squire import config


def test_deep_merge_nested_dicts():
    base = {"a": 1, "b": {"x": 1, "y": 2}}
    override = {"b": {"y": 99, "z": 3}, "c": 4}
    merged = config.deep_merge(base, override)
    assert merged == {"a": 1, "b": {"x": 1, "y": 99, "z": 3}, "c": 4}
    # base must not be mutated
    assert base == {"a": 1, "b": {"x": 1, "y": 2}}


def test_deep_merge_override_replaces_non_dict():
    assert config.deep_merge({"a": [1]}, {"a": [2, 3]}) == {"a": [2, 3]}
    assert config.deep_merge({"a": {"x": 1}}, {"a": "scalar"}) == {"a": "scalar"}


def test_load_config_returns_defaults_when_no_file_exists():
    cfg = config.load_config()
    assert cfg["reader"]["model"] == "llama-3.3-70b-versatile"
    assert cfg["writer"]["target_policy"] == "tmp_by_default"
    assert cfg["reader"]["provider_kind"] == "openai_compatible"


def test_load_config_merges_yaml_over_defaults(tmp_config_path):
    tmp_config_path.write_text(yaml.safe_dump({"reader": {"model": "custom-model"}}))
    cfg = config.load_config()
    assert cfg["reader"]["model"] == "custom-model"
    # other defaults preserved
    assert cfg["reader"]["provider"] == "groq"
    assert cfg["writer"]["max_output_tokens"] == 4096


def test_load_config_respects_legacy_hermes_env_var(tmp_path, monkeypatch):
    cfg_path = tmp_path / "legacy.yaml"
    cfg_path.write_text(yaml.safe_dump({"reader": {"model": "legacy-model"}}))
    monkeypatch.setenv("HERMES_WORKER_CONFIG", str(cfg_path))
    cfg = config.load_config()
    assert cfg["reader"]["model"] == "legacy-model"


def test_load_dotenv_sets_unset_vars_only(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n"
        "SQUIRE_TEST_NEW=fresh\n"
        "SQUIRE_TEST_EXISTING='should-not-overwrite'\n"
        "\n"
        "SQUIRE_TEST_QUOTED=\"with spaces\"\n"
    )
    monkeypatch.setenv("SQUIRE_TEST_EXISTING", "preserved")
    monkeypatch.delenv("SQUIRE_TEST_NEW", raising=False)
    monkeypatch.delenv("SQUIRE_TEST_QUOTED", raising=False)

    config.load_dotenv(env_file)

    assert os.environ["SQUIRE_TEST_NEW"] == "fresh"
    assert os.environ["SQUIRE_TEST_EXISTING"] == "preserved"
    assert os.environ["SQUIRE_TEST_QUOTED"] == "with spaces"


def test_write_default_config_creates_idempotently(tmp_path):
    target = tmp_path / "config.yaml"
    written = config.write_default_config(target)
    assert written == target
    assert target.exists()
    first_contents = target.read_text()

    # second call does not overwrite
    target.write_text("# user edited\n" + first_contents)
    config.write_default_config(target)
    assert target.read_text().startswith("# user edited")
