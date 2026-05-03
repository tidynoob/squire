"""Config loading and dotenv parsing for squire.

Configuration lives in a YAML file (default: ``~/.squire/config.yaml`` or
``~/.hermes/worker_config.yaml`` for backward compat — see ``DEFAULT_CONFIG_PATHS``).
The file is merged on top of ``DEFAULT_CONFIG``; any field not in the file
inherits the default. Environment variables for API keys are loaded from
``~/.hermes/.env`` if present (Hermes-style), and from ``.env`` in the
current directory if present.
"""
from __future__ import annotations

import os
import pathlib
from typing import Any, Dict

import yaml

HERMES_HOME = pathlib.Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
SQUIRE_HOME = pathlib.Path(os.environ.get("SQUIRE_HOME", "~/.squire")).expanduser()

# Search order for config: $SQUIRE_CONFIG, ~/.squire/config.yaml, ~/.hermes/worker_config.yaml.
DEFAULT_CONFIG_PATHS = [
    SQUIRE_HOME / "config.yaml",
    HERMES_HOME / "worker_config.yaml",
]
DEFAULT_LOG_PATH = HERMES_HOME / "logs" / "worker_delegation.jsonl"

DEFAULT_CONFIG: Dict[str, Any] = {
    "reader": {
        "provider": "groq",
        "provider_kind": "openai_compatible",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "max_output_tokens": 800,
        "temperature": 0,
        "max_input_chars": 30000,
        "system_prompt": (
            "You are a precise file-reading worker. Return concise grounded summaries. "
            "Cite file paths when relevant. Do not make final architectural decisions."
        ),
    },
    "writer": {
        "provider": "groq",
        "provider_kind": "openai_compatible",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "max_output_tokens": 4096,
        "temperature": 0.2,
        "max_input_chars": 30000,
        "target_policy": "tmp_by_default",
        "system_prompt": (
            "You are a careful drafting worker. Generate complete draft artifacts. "
            "Do not claim tests were run. Prefer simple maintainable output."
        ),
    },
    "routing": {
        "delegate_file_line_threshold": 400,
        "delegate_file_count_threshold": 3,
        "min_estimated_savings_tokens": 3000,
    },
    "monitoring": {
        "log_path": str(DEFAULT_LOG_PATH),
        "print_metrics": True,
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_dotenv(*paths: pathlib.Path) -> None:
    """Load KEY=VALUE pairs from each file into os.environ if not already set.

    Existing env vars are NOT overwritten. Files that don't exist are skipped.
    Quoted values have their surrounding quotes stripped. Lines starting with
    ``#`` and blank lines are ignored.

    With no arguments, reads from ``$HERMES_HOME/.env`` and ``./.env``. The
    HERMES_HOME location is re-evaluated on each call (not cached at import
    time) so test isolation works.
    """
    if not paths:
        hermes_home = pathlib.Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
        paths = (hermes_home / ".env", pathlib.Path.cwd() / ".env")
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _resolve_config_path() -> pathlib.Path | None:
    """Return the first config file that exists, or None if none do.

    Search order:
        1. $SQUIRE_CONFIG (or $HERMES_WORKER_CONFIG for backward compat)
        2. ~/.squire/config.yaml
        3. ~/.hermes/worker_config.yaml
    """
    explicit = os.environ.get("SQUIRE_CONFIG") or os.environ.get("HERMES_WORKER_CONFIG")
    if explicit:
        return pathlib.Path(explicit).expanduser()
    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate.exists():
            return candidate
    return None


def load_config() -> Dict[str, Any]:
    """Load the full config dict, merging the YAML file (if any) over defaults."""
    cfg_path = _resolve_config_path()
    if cfg_path is None or not cfg_path.exists():
        return DEFAULT_CONFIG
    loaded = yaml.safe_load(cfg_path.read_text()) or {}
    return deep_merge(DEFAULT_CONFIG, loaded)


def write_default_config(path: pathlib.Path | None = None) -> pathlib.Path:
    """Write DEFAULT_CONFIG to disk (idempotent — does not overwrite an existing file).

    Returns the path that was (or would have been) written. Defaults to
    ``~/.squire/config.yaml``.
    """
    target = (path or SQUIRE_HOME / "config.yaml").expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False))
    return target
