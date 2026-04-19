"""PersonaMem dataset adapter.

20 simulated user personas, 589 questions (32k context version),
testing personalization accuracy across 7 question types.

Data structure:
- questions_32k.csv / personamem.json: question entries with persona_id,
  question_type, user_question_or_message, correct_answer, all_options,
  shared_context_id, end_index_in_shared_context
- shared_contexts_32k.jsonl: one JSON object per line, key=shared_context_id,
  value=list of {role, content} conversation turns

Source: https://github.com/bowen-upenn/PersonaMem
HuggingFace: bowen-upenn/PersonaMem
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)


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
        """Parse PersonaMem data into EvalScenarios.

        Each shared_context_id maps to a conversation history. Questions
        reference a context and ask about user preferences/facts.
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

        # Group questions by shared_context_id
        ctx_groups: dict[str, list[dict]] = {}
        for q in questions_data:
            ctx_id = q.get("shared_context_id", "")
            if ctx_id:
                ctx_groups.setdefault(ctx_id, []).append(q)

        scenarios: list[EvalScenario] = []
        for ctx_id, q_items in ctx_groups.items():
            scenario_id = f"personamem_{ctx_id[:12]}"
            turns: list[ConversationTurn] = []
            questions: list[EvalQuestion] = []

            # Build conversation from shared context
            ctx_turns = contexts.get(ctx_id, [])
            # Use end_index from first question to trim context
            end_idx = max(q.get("end_index_in_shared_context", len(ctx_turns)) for q in q_items)
            actual_idx = 0
            for turn in ctx_turns[:end_idx]:
                if isinstance(turn, dict):
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    # Skip system messages (persona descriptions)
                    if role == "system":
                        continue
                    turns.append(
                        ConversationTurn(
                            role=role,
                            content=content,
                            session_id="0",
                            turn_index=actual_idx,
                        )
                    )
                    actual_idx += 1

            # Build questions
            for q_idx, q in enumerate(q_items):
                q_text = q.get("user_question_or_message", "")
                correct = q.get("correct_answer", "")
                # Parse all_options to find the correct answer text
                options_raw = q.get("all_options", "[]")
                try:
                    options = json.loads(options_raw) if isinstance(options_raw, str) else options_raw
                except json.JSONDecodeError:
                    options = []

                # Find the correct option text
                answer_text = correct
                for opt in options:
                    if isinstance(opt, str) and opt.startswith(correct):
                        answer_text = opt
                        break

                category = q.get("question_type", "personalization")
                category = str(category).lower().replace(" ", "_")

                if q_text:
                    questions.append(
                        EvalQuestion(
                            question_id=f"{scenario_id}_q{q_idx}",
                            question=q_text,
                            ground_truth=answer_text,
                            category=category,
                            metadata={"persona_id": str(q.get("persona_id", "")), "topic": q.get("topic", "")},
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

        logger.info(
            "Loaded %d PersonaMem scenarios with %d total questions",
            len(scenarios),
            sum(len(s.questions) for s in scenarios),
        )
        return scenarios
