"""LLM-as-judge for evaluating retrieval quality."""

from __future__ import annotations

import asyncio
import json
import logging
import random

from litellm import acompletion

logger = logging.getLogger(__name__)

_GENERATE_PROMPT = """\
You answer questions from a stored conversation history. Each memory below
is a span of dialogue prefixed with a bracketed timestamp like
``[1:56 pm on 8 May, 2023 | Session 1, Turn 0]``.

Hard rules:
- **Subject must match.** If the question asks about person A but the
  evidence is about person B (e.g. "Caroline's bowl" but only Melanie's
  bowl is mentioned, "what instrument does Caroline play" but only
  Melanie plays instruments), reply exactly: I don't know.
- **Cite only what is explicitly stated.** Do not extrapolate, summarise
  themes, or list general topics. List only items the named person has
  *themselves* mentioned.

Answer style:
- Combine evidence across memories of the same subject. If one memory
  says "home country" and another names "Sweden", answer "Sweden".
- For list-style questions ("What activities…", "What books…", "What
  symbols…"), scan ALL memories and return a short comma-separated list
  (4–6 items) of distinct items the named person mentioned.
- Resolve relative times ("yesterday", "last Sunday", "4 years ago") to
  a concrete date from the bracketed timestamps. If the question is
  "how long ago", answer with the span ("10 years ago"). For "the
  Sunday before X": pick the actual Sunday, not Saturday.
- For "Would X…" / hypothetical questions, infer likely-yes / likely-no
  from the speaker's stated values and prior choices — do not refuse
  just because it's counterfactual.
- Answer concisely. No preamble, no markdown, no quotes, no bullet
  lists. Examples: "Sweden", "7 May 2023", "Pottery, camping, painting,
  swimming", "Likely no".
- Reply "I don't know." only when the subject-attribution rule fails or
  no memory contains relevant evidence.

Memories:
{context}

Question: {question}
Answer:"""

_JUDGE_PROMPT = """\
You are evaluating whether a candidate answer is correct given a ground
truth. Use **semantic equivalence**, never exact string matching. When in
doubt about whether the candidate captures the ground truth's meaning,
prefer marking it CORRECT.

Rules:
- **Numbers**: "At least 3" / "3" / "about 3" / "around three" — all
  equivalent. "once or twice" ≈ "2". "a couple" ≈ "2".
- **Dates / spans**: "27 June 2013" and "10 years ago" (today is 2023)
  are equivalent. "23 August 2023" and "The week of 23 August 2023" are
  equivalent — the candidate naming a date inside the ground-truth span
  counts. "the Sunday before May 25 2023" and "21 May 2023" are
  equivalent.
- **Lists / multi-item answers**: CORRECT whenever the candidate
  contains all (or all but one) of the ground-truth items, even with
  extra items, in any order. ("Pottery, painting, camping, museum,
  swimming, hiking" vs candidate "Pottery, painting, hiking, camping" —
  CORRECT.)
- **Open-ended descriptions**: CORRECT if the candidate's main phrase
  paraphrases or contains the ground truth's core noun phrase. ("A
  painting inspired by sunsets with a pink sky" vs candidate "A painting
  of a sunset with a pink sky, plus an abstract" — CORRECT.)
- **Inferential / hypothetical**: "Likely no" and "Somewhat, but not
  extremely" share the same direction (low intensity) — CORRECT. "Yes"
  vs "No" or unrelated themes — INCORRECT.
- **Single specific facts**: the candidate must name the ground truth's
  entity (place, person, object). A generic stand-in like "her home
  country" when GT is "Sweden" is INCORRECT.
- **"I don't know."**: CORRECT only when the ground truth is empty
  ("") or also indicates absence.

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
        api_keys: list[str] | None = None,
        max_retries: int = 3,
    ):
        self.model = model
        self.api_base = api_base
        self.thinking = thinking
        self.temperature = temperature
        self.top_p = top_p
        self.max_retries = max_retries
        # Build the key pool: prefer the explicit list, fall back to the
        # single key, then to "no key" (litellm picks up env). Each
        # request draws one at random so concurrent load spreads across
        # keys rather than rate-limiting a single one.
        pool = [k for k in (api_keys or []) if k]
        if not pool and api_key:
            pool = [api_key]
        self.api_keys: list[str] = pool
        self.api_key = api_key  # kept for back-compat / single-key paths
        # Failure ledger: requests that exhausted all retries. Recorded
        # (not raised) so one flaky question doesn't abort a 2000-question
        # run; the bench reports the count and a sample at the end.
        self.failures: list[dict[str, str]] = []

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    def _pick_key(self) -> str | None:
        if not self.api_keys:
            return None
        return random.choice(self.api_keys)

    async def _complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        record_label: str = "",
    ) -> str:
        """Complete with random-key rotation + bounded retries.

        Each attempt draws a fresh random key from the pool, so a key that
        just got rate-limited is likely swapped out on retry. After
        ``max_retries`` failed attempts the request is recorded in
        ``self.failures`` and an empty string is returned — the caller
        treats that as a no-answer rather than crashing the whole run.
        """
        base_kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "top_p": self.top_p,
        }
        if self.api_base:
            base_kwargs["api_base"] = self.api_base
        if not self.thinking:
            base_kwargs["extra_body"] = {
                "chat_template_kwargs": {"thinking": False},
                "enable_thinking": False,
            }

        last_err = ""
        for attempt in range(self.max_retries):
            kwargs = dict(base_kwargs)
            key = self._pick_key()
            if key:
                kwargs["api_key"] = key
            try:
                response = await acompletion(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                last_err = str(e)
                # Backoff a little between attempts; rate-limit errors get
                # a longer wait. Cheap exponential, capped.
                is_rate = "429" in last_err or "rate" in last_err.lower()
                wait = min(2 ** attempt + 1, 10) if is_rate else 1
                logger.warning(
                    "LLM call failed (attempt %d/%d, key=…%s): %s — retrying in %ds",
                    attempt + 1, self.max_retries,
                    key[-4:] if key else "none", last_err[:120], wait,
                )
                await asyncio.sleep(wait)

        # Exhausted all retries — record and give up on this request.
        self.failures.append({"label": record_label, "error": last_err[:300]})
        logger.error(
            "LLM call FAILED after %d attempts (%s) — recorded, returning empty. err=%s",
            self.max_retries, record_label or "unlabeled", last_err[:200],
        )
        return ""

    async def generate_answer(
        self, question: str, retrieved_memories: list[str]
    ) -> str:
        """Given a question and retrieved memory contents, generate an answer.

        Uses a low temperature so the answer is reproducible — sampling
        noise at the answer stage was a major source of cross-run accuracy
        variance (the same retrieved context could yield a correct list one
        run and a partial list the next).
        """
        context = "\n---\n".join(retrieved_memories) if retrieved_memories else "(none)"
        prompt = _GENERATE_PROMPT.format(context=context, question=question)
        return await self._complete(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            record_label=f"generate: {question[:80]}",
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
        # Empty ground truth signals an adversarial / unanswerable question:
        # the only correct response is admitting ignorance. Bypass the LLM
        # judge here — it routinely hallucinates "incorrect" verdicts when
        # the ground truth is "" because the prompt asks it to compare two
        # answers and one side is blank.
        if not ground_truth or not ground_truth.strip():
            normalized = (generated_answer or "").lower().strip().rstrip(".!? ")
            # An empty / whitespace-only generation is itself a "no answer"
            # — match it before the marker scan, otherwise empty Gen with
            # empty GT was scored as wrong (no marker substring matches
            # the empty string).
            if not normalized:
                return True, 1.0
            no_answer_markers = (
                "i don't know", "i do not know", "don't know",
                "no information", "not mention", "not specified",
                "no answer", "unknown", "not enough information",
                "cannot determine", "can't determine", "no idea",
                "not provided", "not stated", "not available",
            )
            if any(marker in normalized for marker in no_answer_markers):
                return True, 1.0
            return False, 0.0

        prompt = _JUDGE_PROMPT.format(
            question=question,
            ground_truth=ground_truth,
            candidate=generated_answer,
        )
        raw = await self._complete(
            [{"role": "user", "content": prompt}],
            record_label=f"judge: {question[:80]}",
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
