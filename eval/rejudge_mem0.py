"""Re-score our LoCoMo QA answers with mem0's EXACT judge prompt.

Isolates the judge-prompt confounder: same retrieval (bge-large + rerank),
same generated answers (from eval/reports/locomo_qa/.../run-2), only the
judge prompt changes — ours -> mem0's verbatim prompt from
mem0ai/memory-benchmarks/benchmarks/locomo/prompts.py.

mem0 scores categories 1-4 only (adversarial excluded). NB: mem0's category
NUMBER->name map differs from ours, but cat 5 = adversarial in both, so the
"cat 1-4" subset (1,540 q) is identical. We read the raw category NUMBER from
locomo10.json and apply mem0's preprocess (cat 3 / open-domain -> first ";"
clause) for faithful replication.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

from litellm import acompletion

_ROOT = Path(__file__).resolve().parent
_QA_REPORT = _ROOT / "reports/locomo_qa/locomo-qa/v1/run-2/locomo-qa.json"
_RAW = _ROOT / "data/locomo/locomo10.json"

# mem0's category mapping (benchmarks/locomo/prompts.py)
MEM0_CAT = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}

# ── mem0's EXACT judge system prompt + no-evidence judge template ──
JUDGE_SYSTEM_PROMPT = "You are evaluating conversational AI memory recall. Return JSON only with the format requested."

JUDGE_PROMPT = """Label the generated answer as CORRECT or WRONG.

## Rules

1. **PARTIAL CREDIT**: If the generated answer includes AT LEAST ONE correct item from the gold answer's list, mark CORRECT. Getting 1 out of 2, 2 out of 4, etc. is always acceptable. Only mark WRONG if NONE of the gold answer items appear.

2. **PARAPHRASES COUNT**: Same concept in different words is CORRECT. "Chocolate raspberry tart" = "chocolate cake with raspberries". "Shelter meal service" = "volunteering at a homeless shelter". Emotions and sentiments in the same positive/negative family count as paraphrases: "proud" = "fulfilled" = "accomplished"; "huge success" = "relieved" = "thrilled" (all express positive achievement). Judge semantic meaning, not exact wording.

3. **EXTRA DETAIL IS FINE**: A longer answer that includes the gold answer's key facts plus additional information is CORRECT. Never penalize for being more detailed or specific. If the generated answer adds extra descriptive details beyond the gold answer while still referencing the same core entity or concept, mark CORRECT.

4. **DATE TOLERANCE**: Dates within 14 days of each other are CORRECT. Durations within 50% are CORRECT (e.g., "5 months" matches "six months"; "19 days" matches "two weeks"). Relative dates ("few days before November") match specific dates in the same window. A specific date (e.g., "February 2020") that is consistent with a vague reference (e.g., "a few years ago" relative to 2023) is CORRECT. Converting "last year" to the actual year (e.g., "2022" when conversations are in 2023) is CORRECT.

5. **SEMANTIC OVERLAP**: Judge whether the generated answer addresses the same topic and captures the core idea of the gold answer. Different wording, phrasing, or level of detail should not result in WRONG if the underlying concept matches. For EMOTIONS and FEELINGS questions, answers expressing sentiments in the same valence (positive/negative) about the same event are CORRECT — do not require the exact same emotion word.

6. **SAME REFERENT**: If the generated answer mentions or references the same named entity, character, person, or concept as the gold answer, mark CORRECT — even if the generated answer provides a different physical description or includes additional details. The key question is: does the generated answer identify the same core entity? If yes, it is CORRECT.

7. **FOCUS ON KNOWLEDGE, NOT WORDING**: The goal is to assess whether the system recalled the right fact. Minor differences in specificity, phrasing, or scope should not result in WRONG. Only mark WRONG when the generated answer demonstrates a genuinely different or incorrect understanding.

## ONLY mark WRONG if:
- The generated answer contains ZERO correct items from the gold answer
- The answer addresses a completely different topic

## Question
Question: {question}
Gold answer: {answer}
Generated answer: {response}

Return JSON with "reasoning" (one sentence) and "label" (CORRECT or WRONG). Do NOT include both labels."""


def preprocess_answer(category: int, answer: str) -> str:
    """mem0's preprocess: cat 3 (open-domain) uses only first ';' clause."""
    if category == 3 and ";" in answer:
        return answer.split(";")[0].strip()
    return answer


def _load_triples() -> list[dict]:
    """Join raw (gold + category number) with our generated answers."""
    gen = {
        r["question_id"]: r.get("generated_answer", "")
        for r in json.loads(_QA_REPORT.read_text()).get("individual_results", [])
    }
    raw = json.loads(_RAW.read_text())
    items = list(raw.values()) if isinstance(raw, dict) else raw
    out = []
    for idx, item in enumerate(items):
        for q_idx, q in enumerate(item.get("qa", [])):
            qid = f"locomo_{idx}_q{q_idx}"
            if qid not in gen:
                continue
            out.append({
                "question_id": qid,
                "question": q.get("question", ""),
                "category": int(q.get("category", 0)),
                "gold": str(q.get("answer", "")),
                "generated": gen[qid],
            })
    return out


async def main() -> None:
    cfg = json.loads((_ROOT / "eval.json").read_text())
    model = cfg["llm_model"]
    base = cfg.get("llm_base_url")
    keys = cfg.get("llm_api_key_list") or ([cfg["llm_api_key"]] if cfg.get("llm_api_key") else [])
    conc = int(cfg.get("concurrency", 4))

    triples = _load_triples()
    # mem0 scores categories 1-4 only (exclude adversarial = cat 5).
    scored = [t for t in triples if t["category"] in (1, 2, 3, 4)]
    print(f"loaded {len(triples)} triples; scoring cat 1-4 (mem0 subset): {len(scored)}")

    sem = asyncio.Semaphore(conc)
    results: list[tuple[int, bool]] = []

    async def judge(t: dict) -> None:
        gold = preprocess_answer(t["category"], t["gold"])
        prompt = JUDGE_PROMPT.format(question=t["question"], answer=gold, response=t["generated"])
        msgs = [{"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}]
        async with sem:
            label = "WRONG"
            for attempt in range(4):
                try:
                    kw = {"model": model, "messages": msgs, "temperature": 0.0,
                          "extra_body": {"chat_template_kwargs": {"thinking": False}, "enable_thinking": False}}
                    if base:
                        kw["api_base"] = base
                    if keys:
                        kw["api_key"] = random.choice(keys)
                    r = await acompletion(**kw)
                    txt = (r.choices[0].message.content or "").strip()
                    if txt.startswith("```"):
                        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    label = str(json.loads(txt).get("label", "WRONG")).upper()
                    break
                except Exception:
                    await asyncio.sleep(1 + attempt)
            results.append((t["category"], label == "CORRECT"))

    await asyncio.gather(*[judge(t) for t in scored])

    # Aggregate
    overall = sum(1 for _, ok in results if ok) / len(results) * 100
    print(f"\n=== OUR answers re-scored with mem0's EXACT judge prompt (model={model}) ===")
    print(f"cat 1-4 overall: {overall:.1f}%  (n={len(results)})")
    for cat in (1, 2, 3, 4):
        rows = [ok for c, ok in results if c == cat]
        if rows:
            print(f"  cat {cat} ({MEM0_CAT[cat]:10}): {sum(rows)/len(rows)*100:.1f}%  (n={len(rows)})")


if __name__ == "__main__":
    asyncio.run(main())
