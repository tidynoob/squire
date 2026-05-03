---
name: squire-cheap-worker-delegation
description: Use the squire CLI to reduce main-model token usage for file reading, session/document summarization, and draft generation. Trigger when reading large files, 3+ files, logs, transcripts, Reddit/X/YouTube source packets, agent sessions, or generating boilerplate where the main agent should preserve context. Faithful port of the Claude Code cheap-coworker pattern with `ask-worker`, `worker-write`, `extract-session`, and `worker-stats`.
---

# Squire — cheap-worker delegation

Squire packages the Claude Code cheap-coworker pattern as a standalone CLI. Reach for these scripts before reading large files, transcripts, or batches of source — let the cheap model summarize, keep the main model's context for decisions.

## Tools

- `ask-worker` — sends local files to the configured cheap model and returns a compact summary.
- `worker-write` — generates candidate artifacts, defaulting to `/tmp/squire-worker/` unless `--allow-real-target` is passed.
- `extract-session` — strips JSONL session logs to readable conversation text (no API key needed).
- `worker-stats` — monitors token savings from the JSONL delegation log.

## Configuration

Default config search order: `$SQUIRE_CONFIG` → `~/.squire/config.yaml` → `~/.hermes/worker_config.yaml`. Run `squire init-config` to write a default file.

Each role config (`reader`, `writer`) supports: `model`, `base_url`, `api_key_env`, `max_output_tokens`, `temperature`, `max_input_chars`, `system_prompt`, plus `provider_kind` (default `openai_compatible`).

## Routing rules

Use `ask-worker` instead of directly reading sources when:

- any file is >400 lines
- reading 3+ files for discovery
- reading logs or session transcripts
- summarizing docs/articles/transcripts where exact edits are not needed
- expected main-token savings exceed ~3,000 tokens

Use `worker-write` for:

- test boilerplate
- config scaffolding
- repetitive docs
- draft scripts
- candidate patches or files

Use `extract-session` before summarizing JSONL session files.

Do NOT delegate:

- final architectural decisions
- subtle debugging/judgment
- exact line edits
- credential/auth handling
- destructive shell commands
- final adoption verdicts

## Commands

Reader:

```bash
ask-worker --paths file1.py file2.py --question "Where is X implemented?"
```

Writer (safe default target):

```bash
worker-write --spec "pytest tests for X" --context src/x.py --target test_x_candidate.py
# writes /tmp/squire-worker/test_x_candidate.py unless --allow-real-target is passed
```

Session extraction:

```bash
extract-session ~/.hermes/sessions/session.jsonl -o /tmp/session-clean.md
ask-worker --paths /tmp/session-clean.md docs/architecture.md --question "What doc updates are needed?"
```

Monitoring:

```bash
worker-stats
worker-stats --last 20
```

## Required behavior

- Keep the main agent as manager. Worker reads/drafts; main agent decides/applies.
- Read exact file slices with the main agent's `read_file` before editing based on worker output.
- Check `worker-stats` when asked whether this is saving tokens, or after meaningful use.
- If a worker call saves zero or little tokens, tighten routing thresholds or skip similar future calls.
