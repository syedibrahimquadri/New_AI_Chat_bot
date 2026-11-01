"""Groq chat completion client."""

from __future__ import annotations

import groq

from src.llm.base import LLMError


BACKUP_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")


class GroqClient:
    def __init__(self, env: dict[str, str]) -> None:
        key = env.get("GROQ_API_KEY", "")
        if not key or key.startswith("your_"):
            raise LLMError("GROQ_API_KEY is not set. Add your key to .env, then try again.")
        if not env.get("LLM_MODEL"):
            raise LLMError("LLM_MODEL is not set in .env.")
        self.model = env["LLM_MODEL"]
        self.client = groq.Groq(api_key=key, timeout=30, max_retries=1)

    def complete(self, system: str, user: str) -> str:
        last_error: groq.RateLimitError | None = None
        # Each model has its own quota, so a backup keeps answers instant under load.
        for model in dict.fromkeys((self.model, *BACKUP_MODELS)):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return response.choices[0].message.content or ""
            except groq.RateLimitError as exc:
                last_error = exc
            except groq.NotFoundError as exc:
                if model == self.model:
                    raise LLMError(
                        f"Groq has no model '{model}'. Set LLM_MODEL in .env to an ID from "
                        "https://console.groq.com/docs/models."
                    ) from exc
            except groq.APIError as exc:
                raise LLMError(f"The Groq request failed, so no answer was generated: {exc}") from exc
        raise LLMError(
            "The assistant is busy right now (429 rate limit). Please try again in a minute."
        ) from last_error
