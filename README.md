# squire

**A cheap-LLM squire for your AI coding agent.** Handles bulk reading and drafting so the main model can focus on decisions.

Faithful packaging of the [Claude Code cheap-coworker pattern](https://www.anthropic.com/engineering/claude-code-best-practices). Works with any agent that can spawn a process — Claude Code, Hermes, Cursor, Aider, plain terminal.

```bash
uv pip install git+https://github.com/mitchellgriffin/squire
export GROQ_API_KEY=...
ask-worker --paths src/auth.py src/middleware.py --question "where is the session check?"
```

Returns a 200-token summary instead of dumping 4,000 tokens of source into your main model's context. Across a session, typically 80–95% input-token reduction on file-reading tasks. Run `worker-stats` for your actual numbers.

---

## What it gives you

Four small CLIs and a Python library, sharing one YAML config and one JSONL log:

| Command | What it does |
|---|---|
| `ask-worker` | Read files with a cheap model, return a compact summary. |
| `worker-write` | Draft an artifact (tests, scaffolding, config) with a cheap model. Writes to `/tmp/squire-worker/` by default — main agent reviews before applying. |
| `extract-session` | Convert a JSONL session log into readable markdown. No API key needed. |
| `worker-stats` | Aggregate the JSONL log: how many tokens did delegation save, by role and by model. |

Plus `squire <subcommand>` as a unified front door, and `squire init-config` to write a default config.

## Install

```bash
uv pip install git+https://github.com/mitchellgriffin/squire     # or pip install
export GROQ_API_KEY=sk-...
squire init-config                                                 # writes ~/.squire/config.yaml
```

The four binaries above land on your PATH after install. Squire requires Python 3.11+ and depends on `openai`, `pyyaml`, `python-dotenv`.

### Use a different provider

The default config uses Groq's free-tier `llama-3.3-70b-versatile`, but any OpenAI-compatible API works — just override `base_url` and `api_key_env` per role.

```yaml
reader:
  base_url: http://localhost:11434/v1   # local Ollama
  api_key_env: OLLAMA_API_KEY            # any value, ollama ignores it
  model: llama3.3
```

```yaml
reader:
  base_url: https://api.openai.com/v1   # OpenAI
  api_key_env: OPENAI_API_KEY
  model: gpt-4.1-mini
```

For non-OpenAI-shaped APIs (native Anthropic, Bedrock, etc.) — see [Extending](#extending).

## Use it from your agent

Drop [`skill/SKILL.md`](skill/SKILL.md) into wherever your agent looks for procedural memory:

- Hermes: `~/.hermes/skills/software-development/squire-cheap-worker-delegation/SKILL.md`
- Claude Code: `~/.claude/skills/squire-cheap-worker-delegation/SKILL.md`
- Cursor / Aider / others: paste it into your system prompt or rules file.

The SKILL.md tells the agent when to delegate, when not to, and the exact CLI flags.

## Use it from Python

```python
from squire import ask, write_artifact, extract_session

# Read files, get a compact summary back.
text, metrics = ask(
    paths=["src/auth.py", "src/middleware.py"],
    question="where is the session check?",
)
print(text)
print(f"saved {metrics['estimated_tokens_saved']} tokens")

# Draft an artifact — defaults to /tmp/squire-worker/ for review-before-apply.
target_path, _ = write_artifact(
    spec="pytest tests for the login endpoint, covering 401 + 403 paths",
    target="test_login.py",
    context=["src/auth.py"],
)
print(f"draft written to {target_path}")

# Strip a JSONL session to readable markdown (no API key needed).
extract_session(
    src=Path("~/.hermes/sessions/session.jsonl"),
    out=Path("/tmp/session.md"),
)
```

The full surface is in [`src/squire/__init__.py`](src/squire/__init__.py).

## Architecture

Six source files, separated by concern:

```
src/squire/
  config.py     # YAML loading, dotenv parsing, deep-merge over DEFAULT_CONFIG
  metrics.py    # token estimation + JSONL event logging
  corpus.py     # multi-file reading with a char budget
  session.py    # JSONL → markdown
  providers.py  # Provider ABC + OpenAICompatibleProvider + registry
  client.py     # call_worker — picks a provider, runs the chat call, attaches metrics
  api.py        # ask() and write_artifact() — library entry points
  cli.py        # thin argparse wrappers around api.* / session.* / metrics.*
```

The CLI handlers own no business logic — they parse args and call into `api`. That keeps the library callable from notebooks, scripts, and future agent integrations without going through argparse.

## Extending

### Add a new provider

For non-OpenAI-shaped APIs (native Anthropic, Bedrock, custom internal services), subclass `Provider` and register it:

```python
from squire import Provider, register_provider

class AnthropicProvider(Provider):
    def __init__(self, role_cfg):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.environ[role_cfg["api_key_env"]])
        self.role_cfg = role_cfg

    def chat(self, messages, *, model, temperature, max_tokens):
        # Translate OpenAI-style messages into Anthropic's format here.
        resp = self.client.messages.create(
            model=model,
            messages=[m for m in messages if m["role"] != "system"],
            system=next((m["content"] for m in messages if m["role"] == "system"), ""),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.content[0].text

register_provider("anthropic", AnthropicProvider)
```

Then in your config:

```yaml
reader:
  provider_kind: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
```

### Add a new command

Add a `*_main(argv)` function in `cli.py`, register it as a `[project.scripts]` entry in `pyproject.toml`, and reinstall.

## Running tests

```bash
uv pip install -e ".[dev]"
pytest
```

53 tests cover config, metrics, corpus, session extraction, providers, the call_worker orchestrator, the library API, and the four CLIs.

## Where this came from

The cheap-coworker pattern is from Anthropic's [Claude Code best-practices](https://www.anthropic.com/engineering/claude-code-best-practices) post: keep your expensive model as the manager and delegate bulk reading and drafting to a cheap, fast worker. Squire packages that pattern as a runtime-agnostic CLI so any agent harness can use it.

## License

MIT — see [LICENSE](LICENSE).
