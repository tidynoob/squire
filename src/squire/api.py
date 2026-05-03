"""Library API — call the worker from Python without going through argparse.

These functions are what other code (notebooks, scripts, future plugin shims,
other agent harnesses) should import. The CLI entry points in ``cli.py`` are
thin argparse wrappers that call straight into here.
"""
from __future__ import annotations

import pathlib
from typing import Any, Dict, Iterable, Optional, Tuple

from .client import call_worker
from .config import load_config
from .corpus import file_corpus

PathLike = str | pathlib.Path


def ask(
    paths: Iterable[PathLike],
    question: str,
    *,
    cfg: Optional[Dict[str, Any]] = None,
    max_input_chars: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Send files + question to the reader worker, return ``(answer, metrics)``.

    ``cfg`` defaults to the result of ``load_config()``. ``max_input_chars``
    overrides the role's default. The metrics dict has the same shape as the
    JSONL log events (see ``squire.metrics.estimate_savings``), plus the
    list of files actually consumed under the ``paths`` key.
    """
    cfg = cfg if cfg is not None else load_config()
    role_cfg = cfg["reader"]
    budget = int(max_input_chars or role_cfg.get("max_input_chars", 30000))
    corpus, used_paths, _ = file_corpus(paths, budget)
    text, metrics = call_worker("reader", corpus, question, cfg)
    return text, {**metrics, "paths": used_paths}


def write_artifact(
    spec: str,
    target: PathLike,
    *,
    context: Optional[Iterable[PathLike]] = None,
    cfg: Optional[Dict[str, Any]] = None,
    allow_real_target: bool = False,
    max_input_chars: Optional[int] = None,
) -> Tuple[pathlib.Path, Dict[str, Any]]:
    """Send a spec (+ optional context files) to the writer worker, write output.

    Returns ``(actual_target, metrics)``. By default the writer's ``target_policy``
    is ``tmp_by_default``: the target is rewritten to ``/tmp/squire-worker/<basename>``
    so the worker's output is reviewed by the main agent before being applied for real.
    Pass ``allow_real_target=True`` to write to the literal target path.
    """
    cfg = cfg if cfg is not None else load_config()
    role_cfg = cfg["writer"]

    actual_target = pathlib.Path(target).expanduser()
    if role_cfg.get("target_policy") == "tmp_by_default" and not allow_real_target:
        tmp_root = pathlib.Path("/tmp/squire-worker")
        tmp_root.mkdir(parents=True, exist_ok=True)
        actual_target = tmp_root / actual_target.name

    budget = int(max_input_chars or role_cfg.get("max_input_chars", 30000))
    if context:
        corpus, used_context, _ = file_corpus(context, budget)
    else:
        corpus, used_context = "", []

    spec_msg = (
        "Write the requested artifact. Return only file contents, no markdown fences.\n\n"
        f"SPEC:\n{spec}\n\nTARGET PATH:\n{actual_target}"
    )
    text, metrics = call_worker("writer", corpus, spec_msg, cfg)
    actual_target.parent.mkdir(parents=True, exist_ok=True)
    actual_target.write_text(text)
    return actual_target, {**metrics, "context_paths": used_context, "target": str(actual_target)}
