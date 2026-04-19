"""Global settings model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Hippocampus configuration. All fields from hippocampus.json."""

    # Storage
    storage_type: str = Field(default="sqlite", description="'sqlite' or 'postgresql'")
    db_path: str = Field(default="hippocampus.db", description="SQLite database file path")
    pg_url: str | None = Field(default=None, description="PostgreSQL connection URL")
    pg_pool_min: int = Field(default=2)
    pg_pool_max: int = Field(default=10)

    # Embedding
    embedding_enabled: bool = Field(default=True, description="Set false to disable vector search")
    embedding_provider: str = Field(default="local", description="'local' (sentence-transformers) or 'api' (cloud)")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Model name or litellm model ID")
    embedding_dim: int = Field(default=384, description="Auto-detected at startup")
    embedding_api_key: str | None = Field(default=None, description="API key for cloud embedding (falls back to llm_api_key)")
    embedding_base_url: str | None = Field(default=None, description="API base URL for cloud embedding (falls back to llm_base_url)")

    # LLM
    llm_model: str | None = Field(default=None, description="LLM model identifier (e.g. openai/gpt-4o-mini)")
    llm_base_url: str | None = Field(default=None, description="Custom LLM API base URL")
    llm_api_key: str | None = Field(default=None, description="LLM provider API key")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8321)

    # Scheduler
    consolidation_interval_seconds: int = Field(default=3600)
    consolidation_concurrency: int = Field(default=5, description="Parallel consolidation tasks")
    consolidation_max_tokens: int = Field(default=16000, description="Max tokens per consolidation LLM call (session chunk size)")
    forget_interval_seconds: int = Field(default=1800)

    # Forgetting
    base_ttl_hours: float = Field(default=168.0)
    decay_factor: float = Field(default=0.693)

    # Retrieval weights
    weight_recency: float = Field(default=1.0)
    weight_importance: float = Field(default=1.0)
    weight_relevance: float = Field(default=1.0)

    # Knowledge graph
    kg_path: str = Field(default="knowledge_graph.json")
