"""Token-savings estimation and JSONL event logging.

Token math is deliberately rough: ``estimate_tokens`` uses 4 chars/token, and
``estimate_savings`` assumes the main model would have paid for the full input
if we hadn't delegated. That's an upper bound, but it's the right framing —
the question is "how many tokens did delegation save vs. reading directly?"
not "what is the precise OpenAI billing amount?"
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Any, Dict

from .config import DEFAULT_LOG_PATH


def estimate_tokens(chars: int) -> int:
    """Rough token count for a character count (4 chars per token)."""
    return round(chars / 4)


def estimate_savings(input_chars: int, output_chars: int, overhead_tokens: int = 100) -> Dict[str, Any]:
    """Estimate tokens saved by delegating instead of reading directly.

    Without delegation, the main model would have paid for ``input_chars`` of
    input. With delegation, the main model only pays for the worker's
    ``output_chars`` plus a small ``overhead_tokens`` for the question/instruction.
    """
    input_tokens = estimate_tokens(input_chars)
    output_tokens = estimate_tokens(output_chars)
    main_with_worker = output_tokens + overhead_tokens
    saved = max(0, input_tokens - main_with_worker)
    return {
        "estimated_input_tokens": input_tokens,
        "estimated_worker_output_tokens": output_tokens,
        "estimated_main_tokens_with_worker": main_with_worker,
        "estimated_tokens_saved": saved,
        "estimated_percent_saved": round((saved / input_tokens * 100), 1) if input_tokens else 0,
        "compression_ratio": round((input_tokens / main_with_worker), 1) if main_with_worker else 0,
    }


def log_event(event: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """Append a JSONL event to the configured log path, with a UTC timestamp prepended."""
    path = pathlib.Path(cfg.get("monitoring", {}).get("log_path") or DEFAULT_LOG_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": _dt.datetime.now(_dt.timezone.utc).isoformat(), **event}
    with path.open("a") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
