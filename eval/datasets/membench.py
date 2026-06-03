"""MemBench dataset adapter (ACL 2025).

MemBench probes turn-level memory across 11 categories of multi-turn
conversation. We default to the ``noisy`` category — where distractors
are interleaved with signal — because MemPalace's published numbers
(``docs/analysis/mempalace-benchmark-deep-dive.md §2.4``) sit at 43.4 %
on that slice, the lowest of the 11. It is the slice where any
retrieval-quality improvement shows up most clearly.

Source: https://github.com/import-myself/Membench (``data/FirstAgent/``)

Canonical per-file schema (one JSON file per category):
    Either topic-keyed:
        {"movie": [item, ...], "food": [...], "book": [...]}
    Or role-keyed (a few categories):
        {"roles": [item, ...], "events": [item, ...]}

Per item:
    tid              int
    message_list     list[turn] OR list[list[turn]] — flat OR per-session
                                 turns of shape {user, assistant, time?, place?, sid?}
    QA: {
        question         str
        answer           str
        choices          {A, B, C, D}     — multiple-choice answers
        ground_truth     str              — one of A/B/C/D
        target_step_id   list[list[int]]  — each [sid_or_global_idx, ...]
                                           pointing at the answer-relevant turn(s)
    }

We expose ``target_step_id`` on ``EvalQuestion.metadata`` so the bench
can intersect it with retrieved memory metadata (sid AND global_idx —
the dataset is inconsistent about which one ``target_step_id`` points
at, so we check both, matching MemPalace's
``membench_bench.py:384``).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path

from eval.datasets.base import ConversationTurn, EvalQuestion, EvalScenario

logger = logging.getLogger(__name__)

# Which category JSONs to pull. Keys are the names we accept on the
# adapter constructor; values are the filenames under data/FirstAgent/.
# MemPalace tests all 11; we default to the "noisy" priority but expose
# the full map so an operator can sweep.
CATEGORY_FILES: dict[str, str] = {
    "simple": "simple.json",
    "highlevel": "highlevel.json",
    "knowledge_update": "knowledge_update.json",
    "comparative": "comparative.json",
    "conditional": "conditional.json",
    "noisy": "noisy.json",
    "aggregative": "aggregative.json",
    "highlevel_rec": "highlevel_rec.json",
    "lowlevel_rec": "lowlevel_rec.json",
    "RecMultiSession": "RecMultiSession.json",
    "post_processing": "post_processing.json",
}

_RAW_BASE = (
    "https://raw.githubusercontent.com/import-myself/Membench/main/MemData/FirstAgent"
)

_DEFAULT_CATEGORIES = ("noisy",)
_DEFAULT_TOPIC = "movie"


class MemBenchAdapter:
    """Adapter for import-myself/Membench (FirstAgent topic subsets)."""

    def __init__(
        self,
        categories: tuple[str, ...] | None = None,
        topic: str | None = None,
        limit_per_category: int = 0,
    ) -> None:
        # When the caller doesn't pin categories/topic (the CLI instantiates
        # ``adapter_cls()`` with no args), fall back to env overrides so a
        # full-category sweep needs no code edit:
        #   MEMBENCH_CATEGORIES=all              → every category
        #   MEMBENCH_CATEGORIES=noisy,simple,... → an explicit subset
        #   MEMBENCH_TOPIC=""                    → keep all topic keys
        if categories is None:
            env_cats = os.environ.get("MEMBENCH_CATEGORIES", "").strip()
            if env_cats == "all":
                categories = tuple(CATEGORY_FILES.keys())
            elif env_cats:
                categories = tuple(c.strip() for c in env_cats.split(",") if c.strip())
            else:
                categories = _DEFAULT_CATEGORIES
        if topic is None:
            topic = os.environ.get("MEMBENCH_TOPIC", _DEFAULT_TOPIC)
        bad = [c for c in categories if c not in CATEGORY_FILES]
        if bad:
            raise ValueError(f"Unknown MemBench categories: {bad}")
        self.categories = categories
        self.topic = topic
        self.limit_per_category = limit_per_category

    @property
    def name(self) -> str:
        return "membench"

    async def download(self, data_dir: Path) -> Path:
        """Download the configured category files from raw.githubusercontent.

        Caches each category as-is and writes a consolidated
        ``membench_{categories}_{topic}.json`` so the loader has one
        deterministic path.
        """
        out_dir = data_dir / "membench"
        out_dir.mkdir(parents=True, exist_ok=True)
        cat_tag = "-".join(sorted(self.categories))
        consolidated = out_dir / f"membench_{cat_tag}_{self.topic or 'all'}.json"
        if consolidated.exists():
            logger.info("MemBench data already exists at %s", consolidated)
            return consolidated

        combined: list[dict] = []
        for cat in self.categories:
            fname = CATEGORY_FILES[cat]
            cache_path = out_dir / fname
            if not cache_path.exists():
                url = f"{_RAW_BASE}/{fname}"
                logger.info("Downloading MemBench %s from %s", cat, url)
                try:
                    urllib.request.urlretrieve(url, cache_path)
                except Exception as exc:
                    logger.warning("MemBench: download %s failed: %s", url, exc)
                    continue

            try:
                with open(cache_path) as f:
                    raw = json.load(f)
            except Exception as exc:
                logger.warning("MemBench: parse %s failed: %s", cache_path, exc)
                continue

            # Both schemas are dict-keyed; flatten with the keying
            # preserved as `_topic_key` so downstream filtering works.
            kept_for_cat = 0
            for topic_key, items in raw.items():
                if self.topic and topic_key not in (self.topic, "roles", "events"):
                    continue
                for item in items:
                    item["_category_key"] = cat
                    item["_topic_key"] = topic_key
                    combined.append(item)
                    kept_for_cat += 1
                    if (
                        self.limit_per_category
                        and kept_for_cat >= self.limit_per_category
                    ):
                        break
                if (
                    self.limit_per_category
                    and kept_for_cat >= self.limit_per_category
                ):
                    break
            logger.info("MemBench %s/%s: %d items", cat, self.topic or "all", kept_for_cat)

        consolidated.write_text(json.dumps(combined, ensure_ascii=False, indent=2))
        logger.info("Saved %d MemBench items to %s", len(combined), consolidated)
        return consolidated

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse the consolidated dump into one EvalScenario per item.

        Each turn carries the dataset's local ``sid`` in
        ``ConversationTurn.metadata['sid']`` and its cross-session
        position in ``turn_index`` (the bench refers to this as
        ``global_idx``). Both go onto the hebb memory's metadata at
        ingest time so Hit@k matching can use either.
        """
        raw = json.loads(data_path.read_text())
        items = list(raw.values()) if isinstance(raw, dict) else raw

        scenarios: list[EvalScenario] = []
        for idx, item in enumerate(items):
            category = str(item.get("_category_key", "unknown"))
            topic = str(item.get("_topic_key", "all"))
            tid = item.get("tid", idx)
            scenario_id = f"membench_{category}_{topic}_{tid}_{idx}"

            message_list = item.get("message_list", [])
            qa = item.get("QA", {})
            if not message_list or not qa:
                continue

            # Normalise to list-of-sessions. A flat list-of-turns is a
            # one-session conversation.
            if message_list and isinstance(message_list[0], dict):
                sessions = [message_list]
            else:
                sessions = message_list

            turns: list[ConversationTurn] = []
            global_idx = 0
            for s_idx, session in enumerate(sessions):
                if not isinstance(session, list):
                    continue
                for turn in session:
                    if not isinstance(turn, dict):
                        continue
                    user = turn.get("user") or turn.get("user_message") or ""
                    assistant = (
                        turn.get("assistant") or turn.get("assistant_message") or ""
                    )
                    time_str = turn.get("time") or None
                    sid = turn.get("sid", turn.get("mid", global_idx))
                    try:
                        sid_int = int(sid)
                    except (TypeError, ValueError):
                        sid_int = global_idx

                    # We emit a SINGLE ConversationTurn per round-trip
                    # carrying both halves — the bench ingests them as a
                    # single "[User] X [Assistant] Y" memory matching
                    # MemPalace's setup. Role is set to "user" because
                    # write.py would have keyed off the prompt; the
                    # actual content holds both sides.
                    content_parts: list[str] = []
                    if user:
                        content_parts.append(f"[User] {user}")
                    if assistant:
                        content_parts.append(f"[Assistant] {assistant}")
                    if not content_parts:
                        continue
                    content = " ".join(content_parts)

                    turns.append(
                        ConversationTurn(
                            role="user",
                            content=content,
                            session_id=str(s_idx),
                            turn_index=global_idx,
                            timestamp=time_str,
                            metadata={
                                "sid": sid_int,
                                "global_idx": global_idx,
                                "s_idx": s_idx,
                            },
                        )
                    )
                    global_idx += 1

            if not turns:
                continue

            # target_step_id is a list of lists. The first element of
            # each inner list is the turn pointer (sid OR global_idx,
            # depending on the file). Flatten to a set of ints for fast
            # intersection at scoring time.
            targets: set[int] = set()
            for step in qa.get("target_step_id", []):
                if isinstance(step, list) and step:
                    try:
                        targets.add(int(step[0]))
                    except (TypeError, ValueError):
                        continue
                else:
                    try:
                        targets.add(int(step))
                    except (TypeError, ValueError):
                        continue

            question_text = qa.get("question", "")
            ground_truth = qa.get("ground_truth", "")
            answer_text = qa.get("answer", "")
            if not question_text or not targets:
                continue

            question = EvalQuestion(
                question_id=f"{scenario_id}_q",
                question=question_text,
                ground_truth=str(answer_text or ground_truth),
                category=category,
                evidence=[str(t) for t in sorted(targets)],
                metadata={
                    "category": category,
                    "topic": topic,
                    "tid": tid,
                    "target_step_ids": sorted(targets),
                    "choices": qa.get("choices", {}),
                    "ground_truth_letter": ground_truth,
                },
            )

            scenarios.append(
                EvalScenario(
                    scenario_id=scenario_id,
                    conversations=turns,
                    questions=[question],
                    metadata_extra={"category": category, "topic": topic},
                )
            )

        logger.info(
            "Loaded %d MemBench scenarios across categories %s",
            len(scenarios),
            sorted({s.questions[0].category for s in scenarios}),
        )
        return scenarios
