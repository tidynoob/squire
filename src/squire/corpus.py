"""Read multiple files into a single XML-tagged corpus, truncating at a char budget."""
from __future__ import annotations

import pathlib
from typing import Iterable, List, Tuple


def file_corpus(paths: Iterable[str | pathlib.Path], max_input_chars: int) -> Tuple[str, List[str], int]:
    """Read each path, concatenate as ``<file path='...'>...</file>`` blocks.

    Returns ``(corpus, used_paths, total_chars)``. Stops adding files once the
    char budget is exhausted; the last file included is truncated with a marker.
    """
    docs: List[str] = []
    used_paths: List[str] = []
    total = 0
    for raw in paths:
        p = pathlib.Path(raw).expanduser()
        content = p.read_text(errors="ignore")
        remaining = max_input_chars - total
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n\n[TRUNCATED BY squire max_input_chars]"
        docs.append(f"<file path='{p}'>\n{content}\n</file>")
        used_paths.append(str(p))
        total += len(content)
    return "\n\n".join(docs), used_paths, total
