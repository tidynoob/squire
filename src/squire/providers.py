"""Provider abstraction.

Each squire role (reader, writer, ...) is backed by a Provider — an object
that can produce a chat completion given messages, model, temperature, and
max_tokens. The role config decides which Provider class to instantiate via
the ``provider_kind`` field; ``OpenAICompatibleProvider`` covers Groq,
OpenAI, Ollama, vLLM, and anything else that speaks the OpenAI Chat
Completions API.

To add a new provider (e.g. native Anthropic, Bedrock):

    from squire.providers import Provider, register_provider

    class MyProvider(Provider):
        def __init__(self, role_cfg): ...
        def chat(self, messages, *, model, temperature, max_tokens) -> str: ...

    register_provider("my_kind", MyProvider)

Then set ``provider_kind: my_kind`` in the role config.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Type

from .config import load_dotenv


class Provider(ABC):
    """Base class for chat-completion providers.

    Subclasses receive the role config (a dict from worker_config.yaml) at
    construction and must implement ``chat`` to return the assistant text.
    """

    @abstractmethod
    def __init__(self, role_cfg: Dict[str, Any]) -> None:
        ...

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        ...


class OpenAICompatibleProvider(Provider):
    """Provider for any OpenAI Chat Completions–compatible API.

    Covers OpenAI, Groq, Ollama, vLLM, Together, OpenRouter, anything that
    accepts a ``base_url`` override and an API key. Authentication uses the
    env var named in the role config's ``api_key_env`` (default
    ``GROQ_API_KEY``).
    """

    def __init__(self, role_cfg: Dict[str, Any]) -> None:
        from openai import OpenAI

        self.role_cfg = role_cfg
        load_dotenv()
        api_key_env = role_cfg.get("api_key_env") or "GROQ_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {api_key_env}")
        self.client = OpenAI(api_key=api_key, base_url=role_cfg.get("base_url") or None)

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


# Provider registry — maps the ``provider_kind`` field in role config to a Provider class.
# A *class* is stored, not an instance: get_provider() instantiates per call so
# stateful providers (like an authenticated client) can be re-created cheaply.
REGISTRY: Dict[str, Type[Provider]] = {
    "openai_compatible": OpenAICompatibleProvider,
}


def register_provider(kind: str, provider_cls: Type[Provider]) -> None:
    """Register a Provider class under a name. Overwrites any existing registration."""
    if not isinstance(provider_cls, type) or not issubclass(provider_cls, Provider):
        raise TypeError(f"{provider_cls!r} must be a subclass of Provider")
    REGISTRY[kind] = provider_cls


def get_provider(role_cfg: Dict[str, Any]) -> Provider:
    """Instantiate the provider for a role config.

    The role config selects the provider class via ``provider_kind`` (default
    ``"openai_compatible"`` for backward compat with configs that don't set it).
    """
    kind = role_cfg.get("provider_kind", "openai_compatible")
    cls = REGISTRY.get(kind)
    if cls is None:
        available = ", ".join(sorted(REGISTRY)) or "(none registered)"
        raise ValueError(f"Unknown provider_kind: {kind!r}. Registered: {available}")
    return cls(role_cfg)
