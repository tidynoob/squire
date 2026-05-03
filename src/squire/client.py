"""call_worker — the orchestrator that turns a corpus + question into a worker response.

This module is provider-agnostic: it asks ``providers.get_provider`` for a
Provider instance and calls its ``chat`` method. Reasoning-tag stripping
(`<think>...</think>`) and metric/log emission live here because they're
common to every provider.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Tuple

from .metrics import estimate_savings, log_event
from .providers import get_provider


_REASONING_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning_tags(text: str) -> str:
    """Remove any ``<think>...</think>`` blocks from a model response."""
    return _REASONING_TAG_RE.sub("", text or "").strip()


def call_worker(
    role: str,
    corpus: str,
    question_or_spec: str,
    cfg: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Send (corpus + question) to the worker model for ``role``, return (text, metrics).

    The metrics dict has the same shape as the JSONL log events written by
    older versions of this tool — schema-compatible.
    """
    role_cfg = cfg[role]
    provider = get_provider(role_cfg)
    messages = [
        {"role": "system", "content": role_cfg.get("system_prompt", "")},
        {"role": "user", "content": f"<corpus>\n{corpus}\n</corpus>"},
        {"role": "user", "content": question_or_spec},
    ]
    start = time.time()
    raw = provider.chat(
        messages,
        model=role_cfg["model"],
        temperature=role_cfg.get("temperature", 0),
        max_tokens=role_cfg.get("max_output_tokens", 1000),
    )
    text = strip_reasoning_tags(raw)
    metrics = {
        "role": role,
        "provider": role_cfg.get("provider"),
        "model": role_cfg.get("model"),
        "latency_sec": round(time.time() - start, 2),
        "input_chars": len(corpus) + len(question_or_spec),
        "output_chars": len(text),
        **estimate_savings(len(corpus) + len(question_or_spec), len(text)),
    }
    log_event({"event": role, **metrics}, cfg)
    return text, metrics
