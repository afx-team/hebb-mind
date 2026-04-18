"""LLM-as-judge for evaluating retrieval quality."""

from __future__ import annotations

import asyncio
import json
import logging

from litellm import acompletion

logger = logging.getLogger(__name__)

_GENERATE_PROMPT = """\
Based on the following memories, answer the question concisely.
If the memories don't contain enough information, say "I don't know."

Memories:
{context}

Question: {question}
"""

_JUDGE_PROMPT = """\
You are evaluating whether a candidate answer is correct given a ground truth answer.
Consider semantic equivalence, not exact string matching.
Partial credit: if the candidate captures the core meaning, mark it correct.

Question: {question}
Ground Truth: {ground_truth}
Candidate Answer: {candidate}

Return a JSON object: {{"correct": true/false, "confidence": 0.0-1.0, "reasoning": "..."}}
Only output the JSON, no extra text."""


class LLMJudge:
    """Generate answers from retrieved memories and judge correctness."""

    def __init__(
        self,
        model: str = "openai/gpt-4o-mini",
        api_base: str | None = None,
        api_key: str | None = None,
        thinking: bool = False,
        temperature: float = 0.3,
        top_p: float = 1.0,
    ):
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.thinking = thinking
        self.temperature = temperature
        self.top_p = top_p

    async def _complete(
        self,
        messages: list[dict[str, str]],
        max_retries: int = 5,
    ) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if not self.thinking:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"thinking": False},
                "enable_thinking": False,
            }

        for attempt in range(max_retries):
            try:
                response = await acompletion(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    wait = 2 ** attempt + 1
                    logger.warning(
                        "Rate limited (attempt %d/%d), retrying in %ds",
                        attempt + 1, max_retries, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        # Final attempt — let it raise
        response = await acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def generate_answer(
        self, question: str, retrieved_memories: list[str]
    ) -> str:
        """Given a question and retrieved memory contents, generate an answer."""
        context = "\n---\n".join(retrieved_memories) if retrieved_memories else "(none)"
        prompt = _GENERATE_PROMPT.format(context=context, question=question)
        return await self._complete(
            [{"role": "user", "content": prompt}],
        )

    async def judge_correctness(
        self,
        question: str,
        ground_truth: str,
        generated_answer: str,
    ) -> tuple[bool, float]:
        """Judge whether the generated answer is correct.

        Returns (is_correct, confidence).
        """
        prompt = _JUDGE_PROMPT.format(
            question=question,
            ground_truth=ground_truth,
            candidate=generated_answer,
        )
        raw = await self._complete(
            [{"role": "user", "content": prompt}],
        )
        try:
            # Strip markdown fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            result = json.loads(text)
            return bool(result.get("correct", False)), float(
                result.get("confidence", 0.5)
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Failed to parse judge response: %s", raw[:200])
            return False, 0.0
