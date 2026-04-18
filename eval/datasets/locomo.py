"""LoCoMo dataset adapter.

LoCoMo (Long-term Conversational Memory): 10 multi-session conversations,
each ~300 turns, with questions across 5 reasoning types.

Source: https://github.com/snap-research/locomo
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)

_RAW_URL = (
    "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
)

# LoCoMo category mapping: numeric IDs to readable names
_CATEGORY_MAP = {
    1: "single_hop",
    2: "multi_hop",
    3: "temporal",
    4: "open_ended",
    5: "adversarial",
}


class LoCoMoAdapter:
    """Adapter for the LoCoMo benchmark dataset."""

    @property
    def name(self) -> str:
        return "locomo"

    async def download(self, data_dir: Path) -> Path:
        """Download locomo10.json from GitHub."""
        out_dir = data_dir / "locomo"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "locomo10.json"

        if out_file.exists():
            logger.info("LoCoMo data already exists at %s", out_file)
            return out_file

        logger.info("Downloading LoCoMo from %s", _RAW_URL)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(_RAW_URL, follow_redirects=True)
            resp.raise_for_status()
            out_file.write_bytes(resp.content)

        logger.info("Saved LoCoMo data to %s", out_file)
        return out_file

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse locomo10.json into EvalScenarios.

        LoCoMo format:
        - conversation: dict with speaker_a, speaker_b, session_N_date_time, session_N
        - Each session_N: list of {speaker, dia_id, text}
        - qa: list of {question, answer, evidence, category (1-5)}
        """
        raw = json.loads(data_path.read_text())
        if isinstance(raw, dict):
            items = list(raw.values())
        else:
            items = raw

        scenarios: list[EvalScenario] = []
        for idx, item in enumerate(items):
            scenario_id = f"locomo_{idx}"
            turns: list[ConversationTurn] = []
            questions: list[EvalQuestion] = []

            conv = item.get("conversation", {})
            speaker_a = conv.get("speaker_a", "Speaker A")
            speaker_b = conv.get("speaker_b", "Speaker B")

            # Extract session keys (session_1, session_2, ...) in order
            session_keys = sorted(
                [k for k in conv if k.startswith("session_") and not k.endswith("_date_time")],
                key=lambda k: int(k.split("_")[1]),
            )

            turn_idx = 0
            for session_key in session_keys:
                session_id = session_key.split("_")[1]  # "1", "2", etc.
                date_key = f"{session_key}_date_time"
                session_date = conv.get(date_key, "")

                session_turns = conv.get(session_key, [])
                for t in session_turns:
                    speaker = t.get("speaker", "")
                    text = t.get("text", "")
                    role = speaker_a if speaker == speaker_a else speaker_b
                    turns.append(
                        ConversationTurn(
                            role=role,
                            content=text,
                            session_id=session_id,
                            turn_index=turn_idx,
                            timestamp=session_date,
                        )
                    )
                    turn_idx += 1

            # Parse questions from "qa" field
            for q_idx, q in enumerate(item.get("qa", [])):
                question_text = q.get("question", "")
                answer_text = q.get("answer", "")
                cat_num = q.get("category", 0)
                category = _CATEGORY_MAP.get(cat_num, f"category_{cat_num}")
                evidence = q.get("evidence", [])
                if isinstance(evidence, str):
                    evidence = [evidence]

                questions.append(
                    EvalQuestion(
                        question_id=f"{scenario_id}_q{q_idx}",
                        question=question_text,
                        ground_truth=str(answer_text),
                        category=category,
                        evidence=evidence,
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
            "Loaded %d LoCoMo scenarios with %d total questions",
            len(scenarios),
            sum(len(s.questions) for s in scenarios),
        )
        return scenarios
