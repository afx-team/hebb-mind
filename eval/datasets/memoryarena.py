"""MemoryArena dataset adapter.

MemoryArena evaluates agent memory in **interdependent multi-session
agentic tasks**: each sample is a sequence of subtasks where later
subtasks depend on what the agent did in earlier ones. Failure modes
are different from QA benchmarks like LongMemEval/ConvoMem — reported
SR for off-the-shelf memory systems (Mem0, Letta) is <0.20.

Sources:
- Homepage: https://memoryarena.github.io/
- Paper:    https://arxiv.org/abs/2602.16313
- Dataset:  https://huggingface.co/datasets/ZexueHe/memoryarena  (CC-BY-4.0)

The HF repo ships **5 configs**, each a single ``test`` split:

    config name              rows   subtasks   environment
    bundled_shopping         150    6          WebShop
    progressive_search       221    2-16       Web search + docs
    group_travel_planner     270    5-9        TravelPlanner
    formal_reasoning_math     40    2-16       paper-verified derivations
    formal_reasoning_phys     20    2-12       paper-verified derivations

We download each config as ``{config_name}.json`` so the loader (TBD)
can pick splits a la carte, and write a small ``index.json`` that
records row counts + schema for fast discovery.

``load()`` is intentionally still a stub — the Memory-Agent-Environment
loop runner is the next deliverable; this adapter currently exists to
ship the data to local disk so we can inspect schema and prototype.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from eval.datasets.base import EvalScenario

logger = logging.getLogger(__name__)

_HF_REPO = "ZexueHe/memoryarena"
_CONFIGS = (
    "bundled_shopping",
    "progressive_search",
    "group_travel_planner",
    "formal_reasoning_math",
    "formal_reasoning_phys",
)


class MemoryArenaAdapter:
    """Adapter for the MemoryArena benchmark dataset.

    ``download()`` pulls all 5 configs from Hugging Face. ``load()`` is
    not yet implemented; the agentic-task runner that consumes these
    scenarios is a separate next step (see
    ``eval/benchmarks/memoryarena_bench.py``).
    """

    def __init__(self, configs: tuple[str, ...] = _CONFIGS) -> None:
        bad = [c for c in configs if c not in _CONFIGS]
        if bad:
            raise ValueError(f"Unknown MemoryArena configs: {bad}")
        self.configs = configs

    @property
    def name(self) -> str:
        return "memoryarena"

    async def download(self, data_dir: Path) -> Path:
        """Download every configured split as JSON under ``data_dir/memoryarena/``.

        Returns the directory holding the per-config JSON files. Each
        config caches separately and is skipped if already present, so
        re-running this command is cheap.
        """
        out_dir = data_dir / "memoryarena"
        out_dir.mkdir(parents=True, exist_ok=True)

        from datasets import load_dataset  # type: ignore[import-not-found]

        index: dict[str, dict[str, object]] = {}
        for cfg in self.configs:
            out_file = out_dir / f"{cfg}.json"
            if out_file.exists():
                rows = json.loads(out_file.read_text())
                logger.info(
                    "MemoryArena %s already cached at %s (%d rows)",
                    cfg,
                    out_file,
                    len(rows),
                )
            else:
                logger.info("Downloading MemoryArena config %s from %s", cfg, _HF_REPO)
                ds = load_dataset(_HF_REPO, cfg, split="test")
                rows = ds.to_list()
                out_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
                logger.info("Saved %d rows to %s", len(rows), out_file)
            sample = rows[0] if rows else {}
            index[cfg] = {
                "file": out_file.name,
                "rows": len(rows),
                "columns": sorted(sample.keys()) if isinstance(sample, dict) else [],
            }

        (out_dir / "index.json").write_text(
            json.dumps(
                {"repo": _HF_REPO, "configs": index},
                ensure_ascii=False,
                indent=2,
            )
        )
        logger.info("MemoryArena: wrote index for %d configs to %s", len(index), out_dir)
        return out_dir

    def load(self, data_path: Path) -> list[EvalScenario]:
        raise NotImplementedError(
            "MemoryArena loader is not yet implemented. "
            "Data has been downloaded; the Memory-Agent-Environment loop "
            "runner (see eval/benchmarks/memoryarena_bench.py) is the next step."
        )
