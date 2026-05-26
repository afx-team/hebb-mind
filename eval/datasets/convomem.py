"""ConvoMem dataset adapter.

ConvoMem (Salesforce, 2025) probes memory retrieval over multi-turn
conversations across 6 evidence categories:
    user_evidence              — facts the user stated
    assistant_facts_evidence   — facts the assistant supplied
    changing_evidence          — facts that change across turns
    abstention_evidence        — when the answer should be "I don't know"
    preference_evidence        — implicit user preferences
    implicit_connection_evidence — bridge facts across turns

The dataset on HuggingFace is *not* a flat split; it is a tree of JSON
files under ``core_benchmark/evidence_questions/{category}/N_evidence/``
where N is the number of evidence messages per item (we restrict to
``1_evidence`` to match MemPalace's reported numbers).

Canonical per-file schema:
    {
      "evidence_items": [
        {
          "conversations": [{"messages": [{"text": str, "speaker": str}, ...]}, ...],
          "question": str,
          "answer": str,
          "message_evidences": [{"text": str}, ...]
        },
        ...
      ]
    }

The bench (``convomem_bench.py``) scores **substring containment**: a
question is "correct" iff every evidence text appears (case-insensitive)
inside the concatenation of top-k retrieved memory contents. We surface
each evidence text on ``EvalQuestion.evidence`` so the bench can match
without a second parse pass.

Source: https://huggingface.co/datasets/Salesforce/ConvoMem
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)

# Mirror MemPalace's 6-category list exactly so vs-mempalace.md tables
# can line up category-for-category without name drift.
CATEGORIES = (
    "user_evidence",
    "assistant_facts_evidence",
    "changing_evidence",
    "abstention_evidence",
    "preference_evidence",
    "implicit_connection_evidence",
)

# Preferred evidence slice. MemPalace defaults to 1_evidence (single
# evidence message per question). The ``changing_evidence`` category
# has NO 1_evidence/ directory on HF — it starts at 2_evidence/ by
# design (a "changing fact" requires at least two contradictory
# statements). MemPalace silently skips that category; we fall back to
# the next-available slice so we get coverage on all 6 categories.
_EVIDENCE_SLICE_PREFERENCE = ("1_evidence", "2_evidence")

# Items per category to keep. MemPalace samples 50–100; we default to
# 100 so a full sweep stays cheap (~600 questions total).
_DEFAULT_PER_CATEGORY = 100


class ConvoMemAdapter:
    """Adapter for the Salesforce/ConvoMem evidence_questions benchmark."""

    def __init__(self, per_category: int = _DEFAULT_PER_CATEGORY) -> None:
        self.per_category = per_category

    @property
    def name(self) -> str:
        return "convomem"

    async def download(self, data_dir: Path) -> Path:
        """Download up to ``per_category`` items from each evidence category.

        Writes a single consolidated ``convomem.json`` so the loader has
        one path to open. Each item is annotated with its
        ``_category_key`` so the bench can compute per-category recall.
        """
        out_dir = data_dir / "convomem"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "convomem.json"

        if out_file.exists():
            logger.info("ConvoMem data already exists at %s", out_file)
            return out_file

        from huggingface_hub import hf_hub_download, list_repo_files

        try:
            all_files = list_repo_files(
                repo_id="Salesforce/ConvoMem", repo_type="dataset"
            )
        except Exception as exc:
            raise RuntimeError(f"ConvoMem: list_repo_files failed: {exc}") from exc

        all_items: list[dict] = []
        for category in CATEGORIES:
            files: list[str] = []
            picked_slice = None
            for slice_name in _EVIDENCE_SLICE_PREFERENCE:
                prefix = f"core_benchmark/evidence_questions/{category}/{slice_name}/"
                files = [f for f in all_files if f.startswith(prefix) and f.endswith(".json")]
                if files:
                    picked_slice = slice_name
                    break
            if not files:
                logger.warning(
                    "ConvoMem: no files found for %s in any of %s",
                    category, _EVIDENCE_SLICE_PREFERENCE,
                )
                continue
            logger.info("ConvoMem %s: using %s slice", category, picked_slice)

            cat_items: list[dict] = []
            for fpath in files:
                if len(cat_items) >= self.per_category:
                    break
                try:
                    cached = hf_hub_download(
                        repo_id="Salesforce/ConvoMem",
                        filename=fpath,
                        repo_type="dataset",
                    )
                    with open(cached) as f:
                        data = json.load(f)
                except Exception as exc:
                    logger.warning("ConvoMem: download %s failed: %s", fpath, exc)
                    continue

                for item in data.get("evidence_items", []):
                    item["_category_key"] = category
                    item["_source_file"] = fpath
                    item["_evidence_slice"] = picked_slice
                    cat_items.append(item)
                    if len(cat_items) >= self.per_category:
                        break

            logger.info("ConvoMem %s: %d items", category, len(cat_items))
            all_items.extend(cat_items)

        out_file.write_text(json.dumps(all_items, ensure_ascii=False, indent=2))
        logger.info("Saved %d ConvoMem items to %s", len(all_items), out_file)
        return out_file

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse the consolidated dump into one EvalScenario per item.

        Each item gets its own scenario (its own conversation haystack +
        single question) because conversations don't repeat across items
        — fresh haystack per question matches MemPalace's protocol.
        """
        raw = json.loads(data_path.read_text())
        items = list(raw.values()) if isinstance(raw, dict) else raw

        scenarios: list[EvalScenario] = []
        for idx, item in enumerate(items):
            category = str(item.get("_category_key", "general"))
            scenario_id = f"convomem_{category}_{idx}"
            turns: list[ConversationTurn] = []

            turn_idx = 0
            for conv in item.get("conversations", []):
                for msg in conv.get("messages", []):
                    if not isinstance(msg, dict):
                        continue
                    text = msg.get("text", "")
                    speaker = str(msg.get("speaker", "user")).lower()
                    # Normalise to user/assistant — ConvoMem uses
                    # "user"/"assistant" already, but be defensive.
                    role = "assistant" if speaker in {"assistant", "bot", "system"} else "user"
                    if not text:
                        continue
                    turns.append(
                        ConversationTurn(
                            role=role,
                            content=text,
                            session_id="0",
                            turn_index=turn_idx,
                        )
                    )
                    turn_idx += 1

            question_text = item.get("question", "")
            answer_text = item.get("answer", "")
            evidence_texts = [
                e["text"]
                for e in item.get("message_evidences", [])
                if isinstance(e, dict) and e.get("text")
            ]
            if not question_text or not turns or not evidence_texts:
                continue

            question = EvalQuestion(
                question_id=f"{scenario_id}_q",
                question=question_text,
                ground_truth=str(answer_text),
                category=category,
                evidence=evidence_texts,
                metadata={
                    "evidence_category": category,
                    "source_file": item.get("_source_file", ""),
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
            "Loaded %d ConvoMem scenarios across %d categories",
            len(scenarios),
            len({s.questions[0].category for s in scenarios}),
        )
        return scenarios
