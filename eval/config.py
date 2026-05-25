"""Evaluation configuration."""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class EvalMode(str, Enum):
    RAW = "raw"
    CONSOLIDATED = "consolidated"

_ROOT = Path(__file__).resolve().parent


class EvalSettings(BaseModel):
    """Configuration for evaluation runs."""

    hebb_url: str = Field(default="http://localhost:8321")
    project_root: Path = Field(default_factory=lambda: _ROOT.parent)
    mode: EvalMode = Field(default=EvalMode.RAW)
    llm_model: str = Field(default="openai/gpt-4o-mini")
    llm_base_url: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None)
    llm_thinking: bool = Field(default=False)
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    data_dir: Path = Field(default_factory=lambda: _ROOT / "data")
    reports_dir: Path = Field(default_factory=lambda: _ROOT / "reports")
    batch_size: int = Field(default=50, ge=1)
    search_top_k: int = Field(default=10, ge=1, le=100)
    concurrency: int = Field(default=5, ge=1)
    weight_recency: float = Field(default=1.0, ge=0.0)
    weight_importance: float = Field(default=1.0, ge=0.0)
    weight_relevance: float = Field(default=2.0, ge=0.0)


def load_eval_settings(config_path: Path | None = None) -> EvalSettings:
    """Load settings from eval.json + environment variables.

    Priority: env vars (EVAL_*) > eval.json > defaults.
    """
    data = {}

    path = config_path or _ROOT / "eval.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)

    env_map = {
        "EVAL_HEBB_URL": "hebb_url",
        "EVAL_LLM_MODEL": "llm_model",
        "EVAL_LLM_BASE_URL": "llm_base_url",
        "EVAL_LLM_API_KEY": "llm_api_key",
        "EVAL_DATA_DIR": "data_dir",
        "EVAL_REPORTS_DIR": "reports_dir",
        "EVAL_BATCH_SIZE": "batch_size",
        "EVAL_SEARCH_TOP_K": "search_top_k",
        "EVAL_CONCURRENCY": "concurrency",
    }
    for env_key, field_name in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            data[field_name] = val

    return EvalSettings(**data)
