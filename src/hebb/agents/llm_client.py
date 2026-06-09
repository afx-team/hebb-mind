"""Thin async wrapper around litellm for LLM calls."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from json_repair import repair_json
from litellm import acompletion

from hebb.config.settings import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM client backed by litellm (supports OpenAI, Anthropic, Qwen, GLM, Kimi)."""

    # Per-request timeout + retry. Without a timeout, a single stalled
    # provider response hangs the call indefinitely — over a long batch job
    # (e.g. consolidation) that eventually deadlocks every worker. litellm
    # applies the timeout per attempt and retries transient failures
    # (timeouts, 429s, 5xx) with its own backoff.
    _REQUEST_TIMEOUT_S = 120.0
    _NUM_RETRIES = 3

    def __init__(self, settings: Settings) -> None:
        self.model = settings.llm_model
        self.api_base = settings.llm_base_url
        self.api_key = settings.llm_api_key

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Send a completion request and return the text content."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "timeout": self._REQUEST_TIMEOUT_S,
            "num_retries": self._NUM_RETRIES,
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
    ) -> dict[str, Any]:
        """Complete and parse the response as JSON."""
        text = await self.complete(
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Parse an LLM JSON response, repairing the malformations LLMs emit.

        Strict ``json.loads`` is tried first so a valid response is never
        altered (and never routed through the repairer's lenient typing). On
        failure it falls back to ``json_repair``, which fixes what models
        actually produce: doubled braces (``{{ ... }}`` — observed with GLM-5.1
        under ``response_format=json_object``), truncated/unclosed output
        (``max_tokens`` cutoff), trailing commas, single quotes, and markdown
        fences. Only a ``dict`` result is accepted — a repaired scalar/list
        (e.g. from pure prose) collapses to ``{}`` so a parse failure is never
        confused with a valid empty object by callers that key off
        ``"memories" in decision``.

        Returns:
            The parsed object, or ``{}`` when nothing usable is recovered.
        """
        cleaned = text.strip()
        try:
            result: Any = json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                result = repair_json(cleaned, return_objects=True)
            except Exception:  # json_repair is defensive, but never let it raise here
                result = None

        if isinstance(result, dict):
            return cast("dict[str, Any]", result)

        logger.error("Failed to parse LLM response as JSON: %s", text[:300])
        return {}
