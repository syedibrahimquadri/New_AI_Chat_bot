"""Provider-neutral LLM interface."""

from __future__ import annotations

from typing import Any, Protocol


class LLMError(RuntimeError):
    """A provider failure whose message is safe to show to the user."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


def get_client(settings: dict[str, Any]) -> LLMClient:
    provider = settings["env"]["LLM_PROVIDER"].lower()
    if provider == "groq":
        from src.llm.groq_client import GroqClient

        return GroqClient(settings["env"])
    raise LLMError(f"LLM provider '{provider}' is not implemented yet. Use groq.")
