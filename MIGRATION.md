# Migration from `~/.hermes/scripts/worker_tools.py`

If you were running the original monolithic `worker_tools.py` (the predecessor of squire), this is what changed and how to switch over.

## What changed

**Same:**
- The four CLI commands (`ask-worker`, `worker-write`, `extract-session`, `worker-stats`) and all their flags.
- The YAML config schema. `~/.hermes/worker_config.yaml` keeps working unchanged.
- The JSONL log format at `~/.hermes/logs/worker_delegation.jsonl`. Old events still aggregate correctly with the new `worker-stats`.

**New:**
- Code lives in a real Python package at `~/code/squire/` (or wherever you cloned it), installed as `squire` with `uv pip install -e`.
- Public Python API in `squire.__init__` — call `from squire import ask, write_artifact, extract_session` from any script or notebook.
- `Provider` ABC and registry — drop in a new provider class for non-OpenAI-shaped APIs without touching `call_worker`.
- New default config location: `~/.squire/config.yaml`. The legacy `~/.hermes/worker_config.yaml` is still read as a fallback, so existing setups need no change.
- `extract-session` now works **without** `GROQ_API_KEY` set (it never needed one — the old code happened to import the OpenAI client at module load, which forced the key check).

**Gone:**
- The `[project.scripts]` entry points replace the four hand-written wrappers in `~/.local/bin/` that all execed `python ~/.hermes/scripts/worker_tools.py <subcmd>`. You can replace those wrappers with one-line shims that exec the new venv binaries (see "Cutover" below) or delete them entirely if `~/.hermes/hermes-agent/venv/bin/` is on your PATH.

## Cutover

The recommended cutover preserves a one-step rollback at every stage.

### 1. Install squire alongside the old monolith

```bash
cd ~/code/squire
uv pip install -e ".[dev]"
```

This adds `ask-worker`, `worker-write`, `extract-session`, `worker-stats`, and `squire` binaries to whatever venv is active (e.g. `~/.hermes/hermes-agent/venv/bin/`). The existing `~/.local/bin/` wrappers still resolve to `worker_tools.py`. Two implementations now coexist; nothing user-facing has changed.

### 2. Verify through the new venv binaries directly

```bash
~/.hermes/hermes-agent/venv/bin/ask-worker --paths ~/.hermes/worker_config.yaml --question "What models are configured?"
~/.hermes/hermes-agent/venv/bin/worker-stats
~/.hermes/hermes-agent/venv/bin/extract-session ~/.hermes/sessions/<some-session>.json -o /tmp/clean.md
pytest ~/code/squire/tests/
```

If anything fails: stop. Wrappers and monolith are still intact; nothing is broken.

### 3. Snapshot, then swap the wrappers

```bash
mkdir -p ~/.hermes/scripts/_pre_squire_backup
cp ~/.local/bin/ask-worker ~/.local/bin/worker-write \
   ~/.local/bin/extract-session ~/.local/bin/worker-stats \
   ~/.hermes/scripts/_pre_squire_backup/
cp ~/.hermes/scripts/worker_tools.py ~/.hermes/scripts/test_worker_tools.py \
   ~/.hermes/scripts/_pre_squire_backup/
```

Then replace each `~/.local/bin/` wrapper with:

```sh
#!/bin/sh
exec /Users/<you>/.hermes/hermes-agent/venv/bin/<binary-name> "$@"
```

(One per command, with the matching binary name. `chmod +x` if needed.)

### 4. Update the live SKILL.md (if you had one)

If you previously installed the SKILL.md at `~/.hermes/skills/software-development/hermes-cheap-worker-delegation/SKILL.md`, replace it with the new version at `~/code/squire/skill/SKILL.md` (the rename and updated paths are intentional — operators read the SKILL to know where things live).

### 5. Rollback (if needed)

```bash
cp ~/.hermes/scripts/_pre_squire_backup/{ask-worker,worker-write,extract-session,worker-stats} ~/.local/bin/
```

The old `worker_tools.py` is still in `_pre_squire_backup/` and the old wrappers will exec it. Restore the old SKILL.md from the same backup if you replaced it.

### 6. Cleanup (only after a soak period)

Once you've used the new wrappers normally for a few days:

```bash
rm ~/.hermes/scripts/worker_tools.py ~/.hermes/scripts/test_worker_tools.py
rm -rf ~/.hermes/scripts/_pre_squire_backup
```

Only after this is one-step rollback no longer possible.

## Behavioral diffs to expect

- **`worker-write` default target** is now `/tmp/squire-worker/` (was `/tmp/hermes-worker/`). The `--allow-real-target` flag works the same.
- **Config file search order** now includes `~/.squire/config.yaml` before falling back to `~/.hermes/worker_config.yaml`. `$SQUIRE_CONFIG` takes precedence; the legacy `$HERMES_WORKER_CONFIG` is still honored.
- **Truncation marker** in the file corpus now reads `[TRUNCATED BY squire max_input_chars]` (was `[TRUNCATED BY ask-worker max_input_chars]`). Worker prompts that depended on the exact wording — none should — would notice this.

## What's `Provider` for?

Squire ships with one provider, `OpenAICompatibleProvider`, which covers Groq, OpenAI, Ollama, vLLM, OpenRouter, Together — anything that accepts a `base_url` override. The `Provider` ABC + registry exists so a non-OpenAI-shaped API (native Anthropic, Bedrock) can be added by subclassing and calling `register_provider()`, without modifying `call_worker`. Day one of v0.1 doesn't ship a second provider; the seam is in place for when one is needed.
