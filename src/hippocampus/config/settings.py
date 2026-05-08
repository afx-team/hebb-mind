"""Global settings model."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Hippocampus configuration. All fields from hippocampus.json."""

    model_config = ConfigDict(ignored_types=(property,))

    # Workspace
    home: str | None = Field(
        default=None,
        description="Workspace directory override. If set, data files are stored here "
        "instead of auto-detected location. Can also be set via HIPPOCAMPUS_HOME env var.",
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
            return str(self.home_dir / "hippocampus.db")
        return "hippocampus.db"

    @property
    def kg_path(self) -> str:
        """Knowledge graph file path, derived from workspace root."""
        if self.home_dir:
            return str(self.home_dir / "knowledge_graph.json")
        return "knowledge_graph.json"
