"""longmemeval dataset adapter.

500 questions across 6 types testing long-term memory abilities:
single-session (user/assistant/preference), multi-session reasoning,
temporal reasoning, and knowledge updates.

Source: https://github.com/xiaowu0162/longmemeval
HuggingFace: xiaowu0162/longmemeval

Data format (longmemeval_s):
- Each item: {question_id, question_type, question, answer, question_date,
              haystack_dates, haystack_session_ids, haystack_sessions, answer_session_ids}
- haystack_sessions: list of sessions, each session is list of {role, content} turns
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)


class LongMemEvalAdapter:
    """Adapter for the longmemeval benchmark dataset."""

    @property
    def name(self) -> str:
        return "longmemeval"

    async def download(self, data_dir: Path) -> Path:
        """Download longmemeval dataset via huggingface_hub."""
        out_dir = data_dir / "longmemeval"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "longmemeval_s.json"

        if out_file.exists():
            logger.info("longmemeval data already exists at %s", out_file)
            return out_file

        # Use huggingface_hub to download the raw file (no extension)
        from huggingface_hub import hf_hub_download

        logger.info("Downloading longmemeval via huggingface_hub")
        cached_path = hf_hub_download(
            repo_id="xiaowu0162/longmemeval",
            filename="longmemeval_s",
            repo_type="dataset",
        )
        shutil.copy2(cached_path, out_file)
        logger.info("Saved longmemeval data to %s", out_file)
        return out_file

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse longmemeval data into EvalScenarios.

        Each item is one question with its associated conversation haystack.
        haystack_sessions is a list of sessions, each session is a list of
        {role, content} turns.
        """
        raw = json.loads(data_path.read_text())
        if isinstance(raw, dict):
            items = list(raw.values())
        else:
            items = raw

        scenarios: list[EvalScenario] = []
        for item in items:
            qid = item.get("question_id", "")
            scenario_id = f"longmemeval_{qid}"
            turns: list[ConversationTurn] = []

            # Parse haystack_sessions: list[list[{role, content}]]
            sessions = item.get("haystack_sessions", [])
            haystack_dates = item.get("haystack_dates", [])
            turn_idx = 0
            for s_idx, session in enumerate(sessions):
                session_id = str(s_idx)
                timestamp = haystack_dates[s_idx] if s_idx < len(haystack_dates) else None
                if isinstance(session, list):
                    for turn in session:
                        if isinstance(turn, dict):
                            role = turn.get("role", "user")
                            content = turn.get("content", "")
                        else:
                            role = "user" if turn_idx % 2 == 0 else "assistant"
                            content = str(turn)
                        turns.append(
                            ConversationTurn(
                                role=role,
                                content=content,
                                session_id=session_id,
                                turn_index=turn_idx,
                                timestamp=timestamp,
                            )
                        )
                        turn_idx += 1

            # Each item has exactly one question
            q_text = item.get("question", "")
            a_text = item.get("answer", "")
            category = item.get("question_type", "general")
            category = str(category).lower().replace(" ", "_")

            questions = []
            if q_text:
                questions.append(
                    EvalQuestion(
                        question_id=scenario_id,
                        question=q_text,
                        ground_truth=str(a_text),
                        category=category,
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
            "Loaded %d longmemeval scenarios with %d total questions",
            len(scenarios),
            sum(len(s.questions) for s in scenarios),
        )
        return scenarios
