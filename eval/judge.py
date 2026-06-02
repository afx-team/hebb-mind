"""LLM-as-judge for evaluating retrieval quality."""

from __future__ import annotations

import asyncio
import json
import logging
import random

from litellm import acompletion

logger = logging.getLogger(__name__)

_GENERATE_PROMPT = """\
You answer a user's question using only their stored conversation history.
Each memory below is a span of dialogue prefixed with a bracketed timestamp
like ``[1:56 pm on 8 May, 2023 | Session 1, Turn 0]``.

Before answering, work through the evidence (do this silently):
1. Scan every memory and extract the facts that bear on the question.
2. Reason over those facts together, combining evidence about the same
   subject across memories.
Then output ONLY the final answer — no notes, no preamble, no markdown.

Hard rules:
- **Subject must match.** If the question asks about person A but the
  evidence only concerns person B (e.g. asks about A's instrument but only
  B plays one), reply exactly: I don't know.
- **Cite only what is explicitly stated.** Do not extrapolate, summarise
  themes, or list general topics — only items the named person has
  *themselves* mentioned.
- **Use the most recent value.** When a fact was updated over time (a job,
  a possession, a plan changed in a later session), answer with the LATEST
  state by the timestamps, never the superseded one.

Answer style:
- Combine evidence across memories of the same subject. If one memory says
  "home country" and another names "Sweden", answer "Sweden".
- For list-style questions ("What activities…", "What books…"), scan ALL
  memories and return a short comma-separated list (4–6 distinct items the
  named person mentioned).
- Resolve relative times ("yesterday", "last Sunday", "4 years ago") to a
  concrete date using the bracketed timestamps and the current date shown
  below. For "how long ago", answer with the span ("10 years ago"). For
  "the Sunday before X", pick the actual Sunday, not Saturday.
- For "Would X…" / hypothetical questions, infer likely-yes / likely-no
  from the speaker's stated values and prior choices — do not refuse just
  because it's counterfactual.
- Keep the final answer concise. Examples: "Sweden", "7 May 2023",
  "Pottery, camping, painting, swimming", "Likely no".
- Reply "I don't know." only when the subject-attribution rule fails or no
  memory contains relevant evidence.

Memories:
{context}

Current date: {current_date}
Question: {question}
Answer:"""

# Official LongMemEval reader prompt — verbatim port of the base
# answer_prompt_template in xiaowu0162/LongMemEval src/generation/run_generation.py
# (non-CoT, non-CoN). Neutral / no custom rules, so a QA number produced with
# it can't be accused of being tuned to the benchmark. Used as the headline
# comparable reader; our own _GENERATE_PROMPT remains the tuned alternative
# and serves the other (LoCoMo/ConvoMem) benches.
_OFFICIAL_READER_PROMPT = (
    "I will give you several history chats between you and a user. Please "
    "answer the question based on the relevant chat history.\n\n\nHistory "
    "Chats:\n\n{context}\n\nCurrent Date: {current_date}\nQuestion: "
    "{question}\nAnswer:"
)

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


# ---------------------------------------------------------------------------
# Official LongMemEval answer-correctness judge.
#
# Verbatim port of ``get_anscheck_prompt`` from xiaowu0162/LongMemEval
# (src/evaluation/evaluate_qa.py) so QA accuracy is graded the same way the
# LongMemEval leaderboard / Zep / Mem0 grade it. Per-type nuances:
#   * single-session-preference — the gold "answer" is a personalization
#     RUBRIC, not a literal string to match (this is why a generic string
#     judge scores preference near-zero).
#   * temporal-reasoning — off-by-one day errors are not penalized.
#   * knowledge-update — credit the updated value even if stale info is also
#     present.
#   * abstention (question_id contains "_abs") — reward correctly flagging
#     the question as unanswerable.
# Judged at temperature 0, max_tokens 10; correctness = "yes" in the verdict.
# ---------------------------------------------------------------------------
_ANSCHECK_DEFAULT = (
    "I will give you a question, a correct answer, and a response from a model. "
    "Please answer yes if the response contains the correct answer. Otherwise, "
    "answer no. If the response is equivalent to the correct answer or contains "
    "all the intermediate steps to get the correct answer, you should also "
    "answer yes. If the response only contains a subset of the information "
    "required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}"
    "\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
)
_ANSCHECK_TEMPORAL = (
    "I will give you a question, a correct answer, and a response from a model. "
    "Please answer yes if the response contains the correct answer. Otherwise, "
    "answer no. If the response is equivalent to the correct answer or contains "
    "all the intermediate steps to get the correct answer, you should also "
    "answer yes. If the response only contains a subset of the information "
    "required by the answer, answer no. In addition, do not penalize off-by-one "
    "errors for the number of days. If the question asks for the number of "
    "days/weeks/months, etc., and the model makes off-by-one errors (e.g., "
    "predicting 19 days when the answer is 18), the model's response is still "
    "correct. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\n"
    "Is the model response correct? Answer yes or no only."
)
_ANSCHECK_KNOWLEDGE = (
    "I will give you a question, a correct answer, and a response from a model. "
    "Please answer yes if the response contains the correct answer. Otherwise, "
    "answer no. If the response contains some previous information along with an "
    "updated answer, the response should be considered as correct as long as the "
    "updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}"
    "\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
)
_ANSCHECK_PREFERENCE = (
    "I will give you a question, a rubric for desired personalized response, and "
    "a response from a model. Please answer yes if the response satisfies the "
    "desired response. Otherwise, answer no. The model does not need to reflect "
    "all the points in the rubric. The response is correct as long as it recalls "
    "and utilizes the user's personal information correctly.\n\nQuestion: {}\n\n"
    "Rubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer "
    "yes or no only."
)
_ANSCHECK_ABSTENTION = (
    "I will give you an unanswerable question, an explanation, and a response "
    "from a model. Please answer yes if the model correctly identifies the "
    "question as unanswerable. The model could say that the information is "
    "incomplete, or some other information is given but the asked information is "
    "not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the "
    "model correctly identify the question as unanswerable? Answer yes or no only."
)
_ANSCHECK_BY_TASK = {
    "single-session-user": _ANSCHECK_DEFAULT,
    "single-session-assistant": _ANSCHECK_DEFAULT,
    "multi-session": _ANSCHECK_DEFAULT,
    "temporal-reasoning": _ANSCHECK_TEMPORAL,
    "knowledge-update": _ANSCHECK_KNOWLEDGE,
    "single-session-preference": _ANSCHECK_PREFERENCE,
}


def _anscheck_prompt(
    task: str, question: str, answer: str, response: str, abstention: bool
) -> str:
    """Build the official per-type grading prompt (get_anscheck_prompt)."""
    if abstention:
        return _ANSCHECK_ABSTENTION.format(question, answer, response)
    template = _ANSCHECK_BY_TASK.get(task)
    if template is None:
        logger.warning("anscheck: unknown task %r — using default grading", task)
        template = _ANSCHECK_DEFAULT
    return template.format(question, answer, response)


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
        max_tokens: int | None = None,
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
        if max_tokens is not None:
            base_kwargs["max_tokens"] = max_tokens
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
        self,
        question: str,
        retrieved_memories: list[str],
        question_date: str | None = None,
    ) -> str:
        """Given a question and retrieved memory contents, generate an answer.

        Uses a low temperature so the answer is reproducible — sampling
        noise at the answer stage was a major source of cross-run accuracy
        variance (the same retrieved context could yield a correct list one
        run and a partial list the next).

        ``question_date`` anchors the reader's relative-time resolution
        (LongMemEval ships one per question, e.g. "2023-04-26 (Wed) 10:55").
        Mirrors the official LongMemEval reader, which always passes a
        ``Current Date`` — the biggest single lever on temporal-reasoning
        questions. Callers without a date (LoCoMo/ConvoMem) fall back to
        timestamp-only resolution.
        """
        context = "\n---\n".join(retrieved_memories) if retrieved_memories else "(none)"
        prompt = _GENERATE_PROMPT.format(
            context=context,
            question=question,
            current_date=question_date or "not specified",
        )
        return await self._complete(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            record_label=f"generate: {question[:80]}",
        )

    async def generate_answer_official(
        self,
        question: str,
        retrieved_memories: list[str],
        question_date: str | None = None,
    ) -> str:
        """Answer using the OFFICIAL LongMemEval reader prompt (neutral, no
        custom rules) — see ``_OFFICIAL_READER_PROMPT``. Same low temperature
        as ``generate_answer`` so a run that swaps only the prompt isolates the
        reader-prompt effect. ``question_date`` fills the official
        ``Current Date`` slot.
        """
        context = "\n---\n".join(retrieved_memories) if retrieved_memories else "(none)"
        prompt = _OFFICIAL_READER_PROMPT.format(
            context=context,
            current_date=question_date or "unknown",
            question=question,
        )
        return await self._complete(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            record_label=f"gen-official: {question[:80]}",
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

    async def judge_anscheck(
        self,
        question: str,
        answer: str,
        response: str,
        task: str,
        abstention: bool = False,
    ) -> tuple[bool, float]:
        """Official LongMemEval per-type answer-correctness judge.

        Port of ``get_anscheck_prompt`` (xiaowu0162/LongMemEval). ``answer``
        is the dataset gold (a personalization *rubric* for the preference
        task, an *explanation* for abstention, otherwise the correct answer).
        ``task`` is the LongMemEval ``question_type``; ``abstention`` is
        ``"_abs" in question_id``. Judged at temperature 0, max_tokens 10;
        correctness = ``"yes"`` appears in the verdict. Returns
        ``(is_correct, confidence)`` with confidence ∈ {0.0, 1.0}.
        """
        prompt = _anscheck_prompt(task, question, answer, response, abstention)
        verdict = await self._complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
            record_label=f"anscheck[{task}{'/abs' if abstention else ''}]: {question[:60]}",
        )
        label = "yes" in verdict.lower()
        return label, (1.0 if label else 0.0)
