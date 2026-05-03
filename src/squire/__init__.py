"""squire — a cheap-LLM coworker for AI coding agents.

Public API. See README.md for usage and architecture.
"""
from .api import ask, write_artifact
from .client import call_worker
from .config import DEFAULT_CONFIG, load_config, write_default_config
from .metrics import estimate_savings, estimate_tokens, log_event
from .providers import (
    OpenAICompatibleProvider,
    Provider,
    get_provider,
    register_provider,
)
from .session import extract_session

__version__ = "0.1.0"

__all__ = [
    # high-level API
    "ask",
    "write_artifact",
    "extract_session",
    # config + metrics
    "DEFAULT_CONFIG",
    "load_config",
    "write_default_config",
    "estimate_savings",
    "estimate_tokens",
    "log_event",
    # extension points
    "Provider",
    "OpenAICompatibleProvider",
    "register_provider",
    "get_provider",
    # low-level orchestrator
    "call_worker",
]
