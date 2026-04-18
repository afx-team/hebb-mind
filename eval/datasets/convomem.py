"""ConvoMem dataset adapter.

75,336 QA pairs across 6 evidence categories: fact recall, temporal reasoning,
coreference resolution, verification, understanding, and inference/synthesis.

Source: https://github.com/SalesforceAIResearch/ConvoMem
HuggingFace: Salesforce/ConvoMem
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)


class ConvoMemAdapter:
    """Adapter for the ConvoMem benchmark dataset."""

    @property
    def name(self) -> str:
        return "convomem"

    async def download(self, data_dir: Path) -> Path:
        """Download ConvoMem dataset from HuggingFace."""
        out_dir = data_dir / "convomem"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "convomem.json"

        if out_file.exists():
            logger.info("ConvoMem data already exists at %s", out_file)
            return out_file

        from datasets import load_dataset

        logger.info("Downloading ConvoMem via HuggingFace datasets library")
        ds = load_dataset("Salesforce/ConvoMem")
        # Use first available split
        split_name = list(ds.keys())[0]
        records = [dict(row) for row in ds[split_name]]
        out_file.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        logger.info("Saved %d records to %s", len(records), out_file)
        return out_file

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse ConvoMem data into EvalScenarios."""
        raw = json.loads(data_path.read_text())
        if isinstance(raw, dict):
            items = list(raw.values())
        else:
            items = raw

        # Group items by conversation ID to create scenarios
        conv_groups: dict[str, list[dict]] = {}
        for item in items:
            conv_id = str(item.get("conversation_id", item.get("conv_id", "0")))
            conv_groups.setdefault(conv_id, []).append(item)

        scenarios: list[EvalScenario] = []
        for conv_id, group in conv_groups.items():
            scenario_id = f"convomem_{conv_id}"
            turns: list[ConversationTurn] = []
            questions: list[EvalQuestion] = []

            # Extract conversation context from the first item
            first_item = group[0]
            context = first_item.get("context", first_item.get("conversation", ""))
            if isinstance(context, str) and context:
                # Split context into turns by newlines or speaker markers
                lines = [l.strip() for l in context.split("\n") if l.strip()]
                for t_idx, line in enumerate(lines):
                    role = "user" if t_idx % 2 == 0 else "assistant"
                    turns.append(
                        ConversationTurn(
                            role=role, content=line, session_id="0", turn_index=t_idx
                        )
                    )
            elif isinstance(context, list):
                for t_idx, turn in enumerate(context):
                    if isinstance(turn, dict):
                        role = turn.get("role", "user")
                        content = turn.get("content", "")
                    else:
                        role = "user" if t_idx % 2 == 0 else "assistant"
                        content = str(turn)
                    turns.append(
                        ConversationTurn(
                            role=role, content=content, session_id="0", turn_index=t_idx
                        )
                    )

            # Extract questions from all items in this group
            for q_idx, item in enumerate(group):
                q_text = item.get("question", item.get("query", ""))
                a_text = item.get("answer", item.get("response", ""))
                category = item.get("evidence_category", item.get("category", "general"))
                category = str(category).lower().replace(" ", "_")

                if q_text:
                    questions.append(
                        EvalQuestion(
                            question_id=f"{scenario_id}_q{q_idx}",
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
            "Loaded %d ConvoMem scenarios with %d total questions",
            len(scenarios),
            sum(len(s.questions) for s in scenarios),
        )
        return scenarios
