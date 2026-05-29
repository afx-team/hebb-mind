"""Global settings model."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Hebb Mind configuration. All fields from hebb.json."""

    model_config = ConfigDict(ignored_types=(property,))

    # Workspace
    home: str | None = Field(
        default=None,
        description="Workspace directory override. If set, data files are stored here "
        "instead of auto-detected location. Can also be set via HEBB_HOME env var.",
    )

    # Storage
    storage_type: str = Field(default="sqlite", description="'sqlite' or 'postgresql'")
    pg_url: str | None = Field(default=None, description="PostgreSQL connection URL")
    pg_pool_min: int = Field(default=2)
    pg_pool_max: int = Field(default=10)

    # Embedding
    embedding_enabled: bool = Field(default=True, description="Set false to disable vector search")
    embedding_provider: str = Field(default="local", description="'local' (sentence-transformers) or 'api' (cloud)")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Model name or litellm model ID")
    embedding_dim: int = Field(default=384, description="Auto-detected at startup")
    embedding_api_key: str | None = Field(
        default=None, description="API key for cloud embedding (falls back to llm_api_key)"
    )
    embedding_base_url: str | None = Field(
        default=None, description="API base URL for cloud embedding (falls back to llm_base_url)"
    )
    hf_endpoint: str | None = Field(
        default=None, description="HuggingFace mirror endpoint (e.g. https://hf-mirror.com)"
    )

    # Retrieval pipeline toggles — each path/boost is independently
    # switchable so users can A/B individual contributions and so the
    # eval harness can run ablations without rebuilding the searcher.
    keyword_search_enabled: bool = Field(default=True, description="FTS5/tsvector keyword path in 3-way RRF recall")
    graph_search_enabled: bool = Field(default=True, description="Knowledge-graph tag-match path in 3-way RRF recall")
    lexical_boost_enabled: bool = Field(
        default=True, description="Predicate/quoted-phrase/person-name boost over composite score"
    )
    temporal_boost_enabled: bool = Field(
        default=True, description="Date-proximity boost when query mentions a time anchor"
    )
    graph_expansion_enabled: bool = Field(default=True, description="Post-search graph expansion of top-k tags")

    # Rerank (optional cross-encoder pass after hybrid retrieval)
    rerank_enabled: bool = Field(default=False, description="Enable rerank pass after hybrid retrieval")
    rerank_provider: str = Field(default="local", description="'local' (sentence-transformers CrossEncoder)")
    rerank_model: str = Field(default="BAAI/bge-reranker-base", description="Model name or HF repo id")
    rerank_top_n: int = Field(
        default=30,
        ge=5,
        le=200,
        description="Candidates to rerank before final top_k; auto-bumps searcher overfetch",
    )
    rerank_max_length: int = Field(
        default=512,
        ge=64,
        le=2048,
        description="Max tokens per (query, content) pair fed to the cross-encoder; longer pairs are truncated",
    )

    # Relevance floor for strict recall surfaces (Claude Code hook, MCP). Those
    # callers send strict_recall=True and the server drops any result scoring
    # below this. Does not affect the console Search page, which is unfiltered.
    recall_min_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Min relevance score (0-1) for hook/MCP recall; results below are dropped (console Search unaffected)",
    )

    # LLM
    llm_model: str | None = Field(default=None, description="LLM model identifier (e.g. openai/gpt-4o-mini)")
    llm_base_url: str | None = Field(default=None, description="Custom LLM API base URL")
    llm_api_key: str | None = Field(default=None, description="LLM provider API key")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8321)

    # Scheduler
    consolidation_time: str = Field(
        default="18:00",
        description="Daily consolidation time in 24-hour HH:MM format, using the server's local timezone",
    )
    consolidation_concurrency: int = Field(default=5, description="Parallel consolidation tasks")
    consolidation_max_tokens: int = Field(
        default=16000, description="Max tokens per consolidation LLM call (session chunk size)"
    )
    forget_interval_seconds: int = Field(default=1800)

    # Forgetting
    base_ttl_hours: float = Field(default=168.0)
    decay_factor: float = Field(default=0.693)

    # Retrieval weights
    weight_recency: float = Field(default=1.0)
    weight_importance: float = Field(default=1.0)
    weight_relevance: float = Field(default=1.0)

    # Auto-upgrade
    auto_upgrade_mode: Literal["auto", "notify", "off"] = Field(
        default="notify",
        description="'auto' = upgrade without prompting; 'notify' = banner + OS notification only; 'off' = no check",
    )
    upgrade_grace_seconds: int = Field(
        default=30,
        description="Seconds to wait for in-flight requests before forcing the daemon down during upgrade",
    )

    # Computed (not persisted to JSON) — set by loader after workspace resolution
    home_dir: Path | None = Field(default=None, exclude=True, description="Resolved workspace root directory")

    @field_validator("consolidation_time")
    @classmethod
    def validate_consolidation_time(cls, value: str) -> str:
        """Validate daily consolidation clock time."""
        hour_minute = value.split(":")
        if len(hour_minute) != 2 or not all(part.isdigit() for part in hour_minute):
            raise ValueError("consolidation_time must use HH:MM format")

        hour, minute = (int(part) for part in hour_minute)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("consolidation_time must be a valid 24-hour time")

        return f"{hour:02d}:{minute:02d}"

    @property
    def db_path(self) -> str:
        """SQLite database path, derived from workspace root."""
        if self.home_dir:
            return str(self.home_dir / "hebb.db")
        return "hebb.db"

    @property
    def kg_path(self) -> str:
        """Knowledge graph file path, derived from workspace root."""
        if self.home_dir:
            return str(self.home_dir / "knowledge_graph.json")
        return "knowledge_graph.json"
