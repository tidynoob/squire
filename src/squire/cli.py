"""CLI entry points — thin argparse wrappers around the library API.

Each ``*_main`` function is registered as a console script in pyproject.toml.
The CLI handlers parse arguments, call into ``api`` / ``session`` / ``metrics``,
and handle stdout/stderr formatting. Business logic lives elsewhere.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import List, Optional

from . import api
from .config import DEFAULT_LOG_PATH, load_config, write_default_config
from .session import extract_session


def _print_metrics(metrics: dict, stream=None) -> None:
    """Pretty-print metrics to stderr so stdout stays consumable by pipelines."""
    target = stream if stream is not None else sys.stderr
    print("\n--- worker metrics ---", file=target)
    print(json.dumps(metrics, indent=2), file=target)


# ---------------------------------------------------------------------------
# ask-worker
# ---------------------------------------------------------------------------

def _build_ask_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ask-worker",
        description="Send local files to a cheap reader model and print a compact summary.",
    )
    p.add_argument("--paths", nargs="+", required=True, help="One or more files to read.")
    p.add_argument("--question", required=True, help="What to ask about the files.")
    p.add_argument("--max-input-chars", type=int, help="Override the reader's max_input_chars budget.")
    p.add_argument("--metrics", action="store_true", help="Print token-savings metrics to stderr.")
    return p


def ask_main(argv: Optional[List[str]] = None) -> int:
    args = _build_ask_parser().parse_args(argv)
    cfg = load_config()
    text, metrics = api.ask(args.paths, args.question, cfg=cfg, max_input_chars=args.max_input_chars)
    print(text)
    if args.metrics or cfg.get("monitoring", {}).get("print_metrics"):
        _print_metrics(metrics)
    return 0


# ---------------------------------------------------------------------------
# worker-write
# ---------------------------------------------------------------------------

def _build_write_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worker-write",
        description=(
            "Generate a draft artifact with a cheap writer model. "
            "Defaults to writing into /tmp/squire-worker/ for safety; "
            "pass --allow-real-target to write to the literal path."
        ),
    )
    p.add_argument("--spec", required=True, help="What to write.")
    p.add_argument("--context", nargs="*", help="Optional files to provide as context.")
    p.add_argument("--target", required=True, help="Final target path (or its filename if writing to /tmp/).")
    p.add_argument(
        "--allow-real-target",
        action="store_true",
        help="Write to the literal --target path instead of redirecting to /tmp/squire-worker/.",
    )
    p.add_argument("--max-input-chars", type=int, help="Override the writer's max_input_chars budget.")
    p.add_argument("--metrics", action="store_true", help="Print token-savings metrics to stderr.")
    return p


def write_main(argv: Optional[List[str]] = None) -> int:
    args = _build_write_parser().parse_args(argv)
    cfg = load_config()
    actual, metrics = api.write_artifact(
        args.spec,
        args.target,
        context=args.context,
        cfg=cfg,
        allow_real_target=args.allow_real_target,
        max_input_chars=args.max_input_chars,
    )
    print(str(actual))
    if args.metrics or cfg.get("monitoring", {}).get("print_metrics"):
        _print_metrics(metrics)
    return 0


# ---------------------------------------------------------------------------
# extract-session
# ---------------------------------------------------------------------------

def _build_extract_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="extract-session",
        description="Convert a JSONL session log into readable markdown (user/assistant turns only).",
    )
    p.add_argument("session_jsonl", help="Path to a JSONL session file.")
    p.add_argument("-o", "--output", required=True, help="Where to write the markdown output.")
    p.add_argument("--max-message-chars", type=int, default=8000, help="Truncate any single message at this length.")
    return p


def extract_main(argv: Optional[List[str]] = None) -> int:
    args = _build_extract_parser().parse_args(argv)
    src = pathlib.Path(args.session_jsonl)
    out = pathlib.Path(args.output)
    extract_session(src, out, args.max_message_chars)
    print(str(out.expanduser()))
    return 0


# ---------------------------------------------------------------------------
# worker-stats
# ---------------------------------------------------------------------------

def _build_stats_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worker-stats",
        description="Aggregate token-savings stats from the JSONL delegation log.",
    )
    p.add_argument("--last", type=int, help="Only consider the most recent N events.")
    return p


def stats_main(argv: Optional[List[str]] = None) -> int:
    args = _build_stats_parser().parse_args(argv)
    cfg = load_config()
    path = pathlib.Path(cfg.get("monitoring", {}).get("log_path") or DEFAULT_LOG_PATH).expanduser()
    if not path.exists():
        print("No worker log yet.")
        return 0
    events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if args.last:
        events = events[-args.last:]

    total_saved = sum(e.get("estimated_tokens_saved", 0) for e in events)
    total_input = sum(e.get("estimated_input_tokens", 0) for e in events)
    total_main = sum(e.get("estimated_main_tokens_with_worker", 0) for e in events)
    by_role: dict[str, int] = {}
    by_model: dict[str, int] = {}
    for e in events:
        by_role[e.get("role", "unknown")] = by_role.get(e.get("role", "unknown"), 0) + e.get("estimated_tokens_saved", 0)
        model = e.get("model", "unknown")
        by_model[model] = by_model.get(model, 0) + e.get("estimated_tokens_saved", 0)

    print(json.dumps({
        "events": len(events),
        "estimated_direct_main_tokens": total_input,
        "estimated_main_tokens_with_worker": total_main,
        "estimated_main_tokens_saved": total_saved,
        "estimated_percent_saved": round(total_saved / total_input * 100, 1) if total_input else 0,
        "saved_by_role": by_role,
        "saved_by_model": by_model,
        "log_path": str(path),
    }, indent=2))
    return 0


# ---------------------------------------------------------------------------
# init-config (squire init-config)
# ---------------------------------------------------------------------------

def init_config_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="squire init-config",
        description="Write a default config file to ~/.squire/config.yaml (does not overwrite if it exists).",
    )
    parser.add_argument("--path", help="Custom path for the config file.")
    args = parser.parse_args(argv)
    target = pathlib.Path(args.path).expanduser() if args.path else None
    written = write_default_config(target)
    print(str(written))
    return 0


# ---------------------------------------------------------------------------
# squire dispatcher (single entry point covering all subcommands)
# ---------------------------------------------------------------------------

_DISPATCHER_HELP = """\
usage: squire <command> [options]

Commands:
  ask              Read files with the reader worker (same as `ask-worker`)
  write            Draft an artifact with the writer worker (same as `worker-write`)
  extract-session  JSONL session → readable markdown (same as `extract-session`)
  stats            Aggregate the token-savings log (same as `worker-stats`)
  init-config      Write a default ~/.squire/config.yaml

Run `squire <command> --help` for command-specific options.
"""


def dispatcher_main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the unified ``squire`` command, e.g. ``squire ask --paths ...``."""
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(_DISPATCHER_HELP)
        return 0 if args else 2

    cmd, rest = args[0], args[1:]
    handlers = {
        "ask": ask_main,
        "write": write_main,
        "extract-session": extract_main,
        "stats": stats_main,
        "init-config": init_config_main,
    }
    handler = handlers.get(cmd)
    if handler is None:
        print(f"squire: unknown command {cmd!r}\n", file=sys.stderr)
        print(_DISPATCHER_HELP, file=sys.stderr)
        return 2
    return handler(rest)
