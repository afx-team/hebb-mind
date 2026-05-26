"""LongMemEval dataset adapter.

500 questions across 6 question types testing long-horizon recall:
single-session (user / assistant / preference), multi-session reasoning,
temporal reasoning, and knowledge updates.

Source: https://github.com/xiaowu0162/longmemeval
HuggingFace: ``xiaowu0162/longmemeval`` (file: ``longmemeval_s``)

Canonical schema (per item):
    question_id            str
    question_type          str — one of 6 categories
    question               str
    answer                 str — gold free-text answer (we don't grade against
                                  this; the bench scores session-level recall)
    question_date          str — when the question is asked, e.g. "2023-04-26 (Wed) 10:55"
    haystack_session_ids   list[str] — stable ids the bench will score against
    haystack_dates         list[str] — per-session timestamp
    haystack_sessions      list[list[{role, content}]] — full conversation history
    answer_session_ids     list[str] — the SUBSET of haystack_session_ids that
                                       contain evidence for the question.
                                       THIS is the ground truth for R@k.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)


class LongMemEvalAdapter:
    """Adapter for the LongMemEval benchmark dataset."""

    @property
    def name(self) -> str:
        return "longmemeval"

    async def download(self, data_dir: Path) -> Path:
        """Download longmemeval_s via huggingface_hub.

        The file ships without an extension on HF; we cache a local copy
        with a ``.json`` suffix so subsequent runs short-circuit cleanly.
        """
        out_dir = data_dir / "longmemeval"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "longmemeval_s.json"

        if out_file.exists():
            logger.info("longmemeval data already exists at %s", out_file)
            return out_file

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
        """Parse longmemeval_s into one EvalScenario per question.

        Each scenario carries its own haystack (LongMemEval is structured
        so different questions have different haystacks — there is no
        shared corpus). ``answer_session_ids`` lands on
        ``EvalQuestion.metadata`` so the bench can intersect them with
        retrieved memory ``session_id`` metadata at scoring time.
        """
        raw = json.loads(data_path.read_text())
        items = list(raw.values()) if isinstance(raw, dict) else raw

        scenarios: list[EvalScenario] = []
        for item in items:
            qid = item.get("question_id", "")
            scenario_id = f"longmemeval_{qid}"
            turns: list[ConversationTurn] = []

            sessions = item.get("haystack_sessions", [])
            session_ids = item.get("haystack_session_ids", [])
            haystack_dates = item.get("haystack_dates", [])

            turn_idx = 0
            for s_idx, session in enumerate(sessions):
                # Use the stable id from the dataset, not the positional
                # index — the bench needs to compare against
                # ``answer_session_ids`` which references those same ids.
                session_id = (
                    session_ids[s_idx] if s_idx < len(session_ids) else str(s_idx)
                )
                timestamp = (
                    haystack_dates[s_idx] if s_idx < len(haystack_dates) else None
                )
                if not isinstance(session, list):
                    continue
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

            q_text = item.get("question", "")
            a_text = item.get("answer", "")
            category = str(item.get("question_type", "general")).lower().replace(" ", "_")
            answer_session_ids = [str(s) for s in item.get("answer_session_ids", [])]
            question_date = item.get("question_date", "")

            if not (q_text and turns):
                continue

            question = EvalQuestion(
                question_id=scenario_id,
                question=q_text,
                ground_truth=str(a_text),
                category=category,
                evidence=answer_session_ids,
                metadata={
                    "answer_session_ids": answer_session_ids,
                    "question_date": question_date,
                    "question_type": category,
                },
            )
            scenarios.append(
                EvalScenario(
                    scenario_id=scenario_id,
                    conversations=turns,
                    questions=[question],
                )
            )

        logger.info(
            "Loaded %d longmemeval scenarios with %d total questions",
            len(scenarios),
            sum(len(s.questions) for s in scenarios),
        )
        return scenarios
