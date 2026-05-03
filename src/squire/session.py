"""Convert Hermes/Claude-style JSONL session logs into readable markdown.

Skips system prompts, tool calls, and tool output — keeps only user/assistant
turns. This is useful as a preprocessing step before passing a session to a
worker for summarization, since the raw JSONL contains a lot of structural
noise that wastes tokens.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List, Optional, Tuple


def _message_text(obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Pull (role, text) from a JSONL row if it's a user/assistant turn, else (None, None)."""
    role = obj.get("role") or obj.get("type")
    content = obj.get("content") or obj.get("text") or obj.get("message")
    if isinstance(content, list):
        pieces = []
        for item in content:
            if isinstance(item, dict):
                pieces.append(str(item.get("text") or item.get("content") or ""))
            else:
                pieces.append(str(item))
        content = "\n".join(p for p in pieces if p)
    if not isinstance(content, str) or not content.strip():
        return None, None
    if role in {"user", "assistant"}:
        return role, content.strip()
    return None, None


def extract_session(src: pathlib.Path, out: pathlib.Path, max_message_chars: int = 8000) -> None:
    """Read a JSONL session at ``src``, write a readable markdown file to ``out``.

    Each user/assistant turn becomes a ``## User`` / ``## Assistant`` section
    separated by horizontal rules. Messages longer than ``max_message_chars``
    are truncated with a marker.
    """
    sections: List[str] = []
    for line in src.expanduser().read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        role, text = _message_text(obj)
        if not role or not text:
            continue
        if len(text) > max_message_chars:
            text = text[:max_message_chars] + "\n\n[TRUNCATED BY extract-session]"
        title = "User" if role == "user" else "Assistant"
        sections.append(f"## {title}\n\n{text}")
    out.expanduser().parent.mkdir(parents=True, exist_ok=True)
    out.expanduser().write_text("\n\n---\n\n".join(sections))
