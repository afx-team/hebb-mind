"""Thin async wrapper around litellm for LLM calls."""

from __future__ import annotations

import json
import logging

from litellm import acompletion

from hippocampus.config.settings import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM client backed by litellm (supports OpenAI, Anthropic, Qwen, GLM, Kimi)."""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.llm_model
        self.api_base = settings.llm_base_url
        self.api_key = settings.llm_api_key

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> str:
        """Send a completion request and return the text content."""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if response_format:
            kwargs["response_format"] = response_format

        response = await acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ) -> dict:
        """Complete and parse the response as JSON."""
        text = await self.complete(
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Robust JSON parsing — handles markdown fences, single quotes, etc."""
        # Strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON object from text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            fragment = cleaned[start:end]
            try:
                return json.loads(fragment)
            except json.JSONDecodeError:
                # Try fixing single quotes → double quotes
                try:
                    return json.loads(fragment.replace("'", '"'))
                except json.JSONDecodeError:
                    pass

        logger.error("Failed to parse LLM response as JSON: %s", text[:300])
        return {}
