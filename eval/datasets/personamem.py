"""PersonaMem dataset adapter.

20 simulated user personas, 589 questions (32k context version),
testing personalization accuracy across 7 question types.

Data structure:
- questions_32k.csv / personamem.json: question entries with persona_id,
  question_type, user_question_or_message, correct_answer, all_options,
  shared_context_id, end_index_in_shared_context
- shared_contexts_32k.jsonl: one JSON object per line, key=shared_context_id,
  value=list of {role, content} conversation turns

PersonaMem is a **multiple-choice** benchmark: ``correct_answer`` is a letter
like ``(c)`` and ``all_options`` is a list of four lettered candidate
responses. The benchmark scores exact-match on the chosen letter (see
``eval/benchmarks/personamem_bench.py``), so the adapter must surface the
options and the gold letter on each question, not just a free-text string.

Two data quirks the adapter handles:

1. ``all_options`` is serialized inconsistently — valid JSON
   (double-quoted) for ~286 rows and a Python ``repr`` (single-quoted) for
   ~303. ``json.loads`` silently fails on the repr rows; we fall back to
   ``ast.literal_eval`` so all 589 rows parse to four lettered options.
2. Each question is asked at a specific point in its conversation
   (``end_index_in_shared_context``). To stay faithful to the official
   protocol and avoid leaking *future* turns of the same persona into
   retrieval, questions are grouped into one scenario per
   ``(shared_context_id, end_index)`` bucket — the scenario's conversation
   is exactly ``turns[:end_index]``. The benchmark gives each scenario its
   own partition and retrieves partition-scoped, so a question never sees
   another bucket's (or another persona's) turns.

Source: https://github.com/bowen-upenn/PersonaMem
HuggingFace: bowen-upenn/PersonaMem
"""

from __future__ import annotations

import ast
import json
import logging
import re
import shutil
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)

# Leading "(a)" / "(b)" / ... label on an option or the correct_answer.
_LETTER_RE = re.compile(r"^\s*\(([a-zA-Z])\)")


def _parse_options(raw: object) -> list[str]:
    """Parse ``all_options`` into a list of option strings.

    The field is sometimes valid JSON (double-quoted) and sometimes a
    Python ``repr`` (single-quoted). Try JSON first, then
    ``ast.literal_eval``; return ``[]`` if neither yields a list.
    """
    if isinstance(raw, list):
        return [str(o) for o in raw]
    if not isinstance(raw, str):
        return []
    for parse in (json.loads, ast.literal_eval):
        try:
            value = parse(raw)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, list):
            return [str(o) for o in value]
    return []


def _option_letter(text: str) -> str | None:
    """Extract the leading option letter (lowercased), e.g. "(c)" -> "c"."""
    m = _LETTER_RE.match(text or "")
    return m.group(1).lower() if m else None


class PersonaMemAdapter:
    """Adapter for the PersonaMem benchmark dataset."""

    @property
    def name(self) -> str:
        return "personamem"

    async def download(self, data_dir: Path) -> Path:
        """Download PersonaMem dataset (questions + shared contexts)."""
        out_dir = data_dir / "personamem"
        out_dir.mkdir(parents=True, exist_ok=True)
        questions_file = out_dir / "personamem.json"
        contexts_file = out_dir / "shared_contexts_32k.jsonl"

        if questions_file.exists() and contexts_file.exists():
            logger.info("PersonaMem data already exists at %s", out_dir)
            return out_dir

        from huggingface_hub import hf_hub_download

        # Download questions via datasets library
        if not questions_file.exists():
            try:
                from datasets import load_dataset

                logger.info("Downloading PersonaMem questions via datasets library")
                ds = load_dataset("bowen-upenn/PersonaMem")
                split_name = list(ds.keys())[0]
                records = [dict(row) for row in ds[split_name]]
                questions_file.write_text(json.dumps(records, ensure_ascii=False, indent=2))
                logger.info("Saved %d question records", len(records))
            except Exception as e:
                logger.warning("datasets library failed (%s), trying direct download", e)
                cached = hf_hub_download(
                    repo_id="bowen-upenn/PersonaMem",
                    filename="questions_32k.csv",
                    repo_type="dataset",
                )
                shutil.copy2(cached, out_dir / "questions_32k.csv")

        # Download shared contexts
        if not contexts_file.exists():
            logger.info("Downloading PersonaMem shared contexts")
            cached = hf_hub_download(
                repo_id="bowen-upenn/PersonaMem",
                filename="shared_contexts_32k.jsonl",
                repo_type="dataset",
            )
            shutil.copy2(cached, contexts_file)
            logger.info("Saved shared contexts to %s", contexts_file)

        return out_dir

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse PersonaMem data into MCQ EvalScenarios.

        One scenario per ``(shared_context_id, end_index)`` bucket so each
        question's haystack is exactly the conversation prefix it was asked
        after. Questions carry their lettered options and gold letter in
        ``metadata`` for the MCQ scorer.
        """
        # data_path is the directory
        if data_path.is_dir():
            questions_path = data_path / "personamem.json"
            contexts_path = data_path / "shared_contexts_32k.jsonl"
        else:
            questions_path = data_path
            contexts_path = data_path.parent / "shared_contexts_32k.jsonl"

        # Load questions
        questions_data = json.loads(questions_path.read_text())

        # Load shared contexts: each line is a JSON object {context_id: [turns]}
        contexts: dict[str, list[dict]] = {}
        if contexts_path.exists():
            for line in contexts_path.read_text().strip().split("\n"):
                if line.strip():
                    obj = json.loads(line)
                    for ctx_id, turns in obj.items():
                        contexts[ctx_id] = turns

        # Group questions into (context_id, end_index) buckets. Each bucket
        # becomes one scenario whose conversation is turns[:end_index] — so
        # retrieval for a question never sees future turns of the persona.
        buckets: dict[tuple[str, int], list[dict]] = {}
        ctx_order: dict[str, int] = {}
        for q in questions_data:
            ctx_id = q.get("shared_context_id", "")
            if not ctx_id:
                continue
            ctx_turns = contexts.get(ctx_id, [])
            end_idx = q.get("end_index_in_shared_context", len(ctx_turns))
            try:
                end_idx = int(end_idx)
            except (TypeError, ValueError):
                end_idx = len(ctx_turns)
            end_idx = max(0, min(end_idx, len(ctx_turns)))
            ctx_order.setdefault(ctx_id, len(ctx_order))
            buckets.setdefault((ctx_id, end_idx), []).append(q)

        scenarios: list[EvalScenario] = []
        skipped_no_options = 0
        for (ctx_id, end_idx), q_items in buckets.items():
            cidx = ctx_order[ctx_id]
            # Partition ids must match ^mem_[a-z0-9_]+$ (enforced by the
            # partitions API), so the scenario id — which doubles as its
            # partition — carries the mem_ prefix.
            scenario_id = f"mem_personamem_c{cidx}_e{end_idx}"

            # Build conversation = raw turns[:end_index], skipping system
            # messages (persona descriptions). end_index indexes into the
            # raw turn list, so slice first, then drop system turns.
            turns: list[ConversationTurn] = []
            actual_idx = 0
            for turn in contexts.get(ctx_id, [])[:end_idx]:
                if not isinstance(turn, dict):
                    continue
                role = turn.get("role", "user")
                if role == "system":
                    continue
                turns.append(
                    ConversationTurn(
                        role=role,
                        content=turn.get("content", ""),
                        session_id=None,
                        turn_index=actual_idx,
                    )
                )
                actual_idx += 1

            questions: list[EvalQuestion] = []
            for q_idx, q in enumerate(q_items):
                q_text = q.get("user_question_or_message", "")
                if not q_text:
                    continue

                options = _parse_options(q.get("all_options", "[]"))
                gold_letter = _option_letter(q.get("correct_answer", ""))
                if not options or gold_letter is None:
                    skipped_no_options += 1
                    continue

                # Gold option text (for reporting / error analysis).
                answer_text = q.get("correct_answer", "")
                for opt in options:
                    if _option_letter(opt) == gold_letter:
                        answer_text = opt
                        break

                category = str(q.get("question_type", "personalization")).lower().replace(" ", "_")
                questions.append(
                    EvalQuestion(
                        question_id=f"{scenario_id}_q{q_idx}",
                        question=q_text,
                        ground_truth=answer_text,
                        category=category,
                        metadata={
                            "options": options,
                            "answer_letter": gold_letter,
                            "persona_id": str(q.get("persona_id", "")),
                            "topic": q.get("topic", ""),
                            "question_type": category,
                            "end_index": end_idx,
                            "distance_to_ref_proportion": q.get(
                                "distance_to_ref_proportion_in_context", ""
                            ),
                        },
                    )
                )

            if turns and questions:
                scenarios.append(
                    EvalScenario(
                        scenario_id=scenario_id,
                        conversations=turns,
                        questions=questions,
                    )
                )

        if skipped_no_options:
            logger.warning(
                "PersonaMem: skipped %d questions with unparseable options/letter",
                skipped_no_options,
            )
        logger.info(
            "Loaded %d PersonaMem scenarios (one per context×cut-point) with %d total questions",
            len(scenarios),
            sum(len(s.questions) for s in scenarios),
        )
        return scenarios
