"""Global settings model."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Bounds for the retention-score forgetting parameters. ``half_life_days`` is
# capped at ~10 years; the coefficients keep the linear half-life stretch sane;
# ``threshold`` is an open interval (0, 1) — the retention level below which a
# memory is forgotten.
FORGETTING_HALF_LIFE_MAX_DAYS = 3650.0
FORGETTING_COEFF_MAX = 10.0


class PartitionForgettingOverride(BaseModel):
    """Per-partition forgetting policy stored in hebb.json (config, not data).

    Forgetting uses the retention-score model::

        eff_half_life = half_life_days · (1 + k_importance·(importance/10) + k_access·(access_count/10))
        retention(idle) = exp(−idle_days / eff_half_life)
        forget when retention < threshold

    A ``None`` numeric field inherits the partition's region default (see
    ``REGION_FORGET_DEFAULTS``) or, failing that, the global ``Settings`` value;
    ``enabled=False`` exempts the partition from the forgetting sweep entirely.
    """

    half_life_days: float | None = Field(default=None, gt=0, le=FORGETTING_HALF_LIFE_MAX_DAYS)
    k_importance: float | None = Field(default=None, ge=0, le=FORGETTING_COEFF_MAX)
    k_access: float | None = Field(default=None, ge=0, le=FORGETTING_COEFF_MAX)
    threshold: float | None = Field(default=None, gt=0, lt=1)
    enabled: bool = Field(default=True)


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

    # Embedding — custom HTTP (API provider only). When embedding_provider == "api"
    # and embedding_api_mode == "custom", vectors come from a fully user-defined
    # HTTP request instead of litellm. The body is a JSON template: "{{input}}" is
    # substituted with a JSON array of all texts (one batched request); "{{text}}"
    # is substituted with one JSON-escaped string (one request per text). The
    # response vector(s) are read via embedding_http_response_path.
    embedding_api_mode: Literal["litellm", "custom"] = Field(
        default="litellm",
        description="API embedding transport: 'litellm' (model ID + base_url) or 'custom' (raw HTTP request)",
    )
    embedding_http_method: str = Field(default="POST", description="HTTP method for custom embedding requests")
    embedding_http_url: str | None = Field(default=None, description="Full endpoint URL for custom HTTP embedding")
    embedding_http_headers: str | None = Field(
        default=None, description="HTTP headers for custom embedding, as a JSON object string (may contain secrets)"
    )
    embedding_http_body: str | None = Field(
        default=None,
        description="Request body template (JSON) with a '{{input}}' (array) or '{{text}}' (string) placeholder",
    )
    embedding_http_response_path: str = Field(
        default="data.*.embedding",
        description="Dot path with '*' array wildcards to the embedding vector(s) in the JSON response",
    )

    # Retrieval pipeline toggles — each path/boost is independently
    # switchable so users can A/B individual contributions and so the
    # eval harness can run ablations without rebuilding the searcher.
    vector_search_enabled: bool = Field(default=True, description="Embedding vector path in 3-way RRF recall")
    keyword_search_enabled: bool = Field(default=True, description="FTS5/tsvector keyword path in 3-way RRF recall")
    graph_search_enabled: bool = Field(default=True, description="Knowledge-graph tag-match path in 3-way RRF recall")
    lexical_boost_enabled: bool = Field(
        default=True, description="Predicate/quoted-phrase/person-name boost over composite score"
    )
    temporal_boost_enabled: bool = Field(
        default=True, description="Date-proximity boost when query mentions a time anchor"
    )
    graph_expansion_enabled: bool = Field(default=True, description="Post-search graph expansion of top-k tags")
    keyword_blend_enabled: bool = Field(
        default=True,
        description="Blend re-rank keyword channel (BM25 magnitude × coverage/proximity) — lifts intrinsic top-1/top-k",
    )

    # Rerank — cross-encoder pass after hybrid retrieval. ON by default: a
    # local CrossEncoder reading (query, content) jointly is the single
    # highest-impact retrieval-quality lever measured across LoCoMo /
    # LongMemEval / MemBench (+14–17pp Recall@1 / Hit@1, R@10 gains too).
    # Degrades gracefully — if the model can't load, create_reranker returns
    # None and the searcher falls back to the calibrated hybrid score with no
    # error. Set false to skip the model download + ~per-query rerank latency.
    rerank_enabled: bool = Field(
        default=True, description="Cross-encoder rerank after hybrid retrieval (graceful fallback if model unavailable)"
    )
    rerank_provider: str = Field(default="local", description="'local' (sentence-transformers CrossEncoder)")
    rerank_model: str = Field(default="BAAI/bge-reranker-base", description="Model name or HF repo id")
    rerank_top_n: int = Field(
        default=30,
        ge=5,
        le=200,
        description="Candidates to rerank before final top_k; auto-bumps searcher overfetch",
    )

    # Relevance floor for strict recall surfaces (Claude Code hook, MCP). Those
    # callers send strict_recall=True and the server drops any result scoring
    # below this. Does not affect the console Search page, which is unfiltered.
    # Adjusted from 0.8 to 0.6 based on LoCoMo eval (1978 queries): 0.8 caused
    # 39% empty-recall queries; 0.6 gives R@10=91.5% with 1.0% empty fraction.
    recall_min_score: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Min relevance score (0-1) for hook/MCP recall; results below are dropped (console Search unaffected). "
        "Recommended: 0.6 (R@10=91.5%, empty fraction=1.0% on LoCoMo eval).",
    )
    # DEPRECATED: This field is retained only as an emergency rollback switch.
    # New code should use ``filter_score`` for composite-score filtering instead.
    # Original purpose: translate the composite floor to the cross-encoder sigmoid
    # scale for reranked entries, but eval (LoCoMo, 1978 queries) proved sigmoid
    # scores are unsuitable for hard filtering — 39% of queries returned empty sets.
    # See: eval/reports/threshold_calibration/threshold_calibration_review_v2.md
    rerank_floor_ratio: float = Field(
        default=0.625,
        ge=0.0,
        le=1.0,
        description="[DEPRECATED] Retained as emergency rollback only. Use filter_score instead. "
        "Original purpose: translate composite floor to cross-encoder sigmoid scale "
        "for reranked entries. Eval proved sigmoid scores unsuitable for hard filtering.",
    )
    # Composite-score filter threshold: when strict_recall is active, results
    # with composite score below this value are dropped. Unlike the old
    # rerank_floor_ratio approach, this filters on the composite scale directly,
    # avoiding the sigmoid-score mismatch that caused 39% empty-recall queries.
    # Recommended: 0.6 (R@10=91.5%, empty frac=1.0% on LoCoMo eval).
    filter_score: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Composite-score filter threshold (0-1) for strict recall; "
        "results below this score are dropped. Recommended: 0.6 "
        "(R@10=91.5%, empty fraction=1.0% on LoCoMo eval).",
    )
    recall_hook_min_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Per-deployment min_score override for the recall hook; "
        "None = use strict_recall (global recall_min_score)",
    )

    # Retrieval-induced strengthening ("提取即强化" / testing effect): when a
    # /search returns hits, bump their access_count + last_accessed_at so the
    # forgetting TTL and recency ranking treat recalled memories as alive. The
    # dynamic TTL already rewards access_count/recency, but nothing on the search
    # path fed it — only GET /memories/{id} did — so frequently-recalled memories
    # decayed as if never used. Disabled by benchmarks (they run on a fixed
    # snapshot; write-back would make recency/ordering depend on query order).
    recall_strengthening_enabled: bool = Field(
        default=True,
        description="On a search hit, strengthen returned memories (access_count + recency) so recall feeds the forgetting TTL",
    )

    # LLM
    llm_model: str | None = Field(default=None, description="LLM model identifier (e.g. openai/gpt-4o-mini)")
    llm_base_url: str | None = Field(default=None, description="Custom LLM API base URL")
    llm_api_key: str | None = Field(default=None, description="LLM provider API key")

    # Server
    host: str = Field(
        default="127.0.0.1",
        description="Bind address. Defaults to loopback (127.0.0.1) for security — the server has "
        "no authentication, so remote exposure (e.g. 0.0.0.0) is an explicit opt-in and should be "
        "paired with a firewall/reverse proxy.",
    )
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
    consolidation_drain_empty_sources: bool = Field(
        default=True,
        description=(
            "When a session consolidation returns no memories (the LLM judged the "
            "content low-value, e.g. small talk), drain those working memories from "
            "the inbox instead of keeping them forever. Disable to keep all sources "
            "(legacy behavior). A garbled/unparseable LLM response is always kept, "
            "never drained."
        ),
    )
    forget_interval_seconds: int = Field(default=1800)

    # Forgetting — retention-score model (see PartitionForgettingOverride). These
    # are the global fallbacks for user partitions / unknown regions; the built-in
    # cortical regions have their own defaults in REGION_FORGET_DEFAULTS.
    half_life_days: float = Field(default=60.0, gt=0, le=FORGETTING_HALF_LIFE_MAX_DAYS)
    k_importance: float = Field(default=2.0, ge=0, le=FORGETTING_COEFF_MAX)
    k_access: float = Field(default=1.5, ge=0, le=FORGETTING_COEFF_MAX)
    forget_threshold: float = Field(default=0.3, gt=0, lt=1)
    # Hard floor (days) on a memory's retained lifetime, so a pathological
    # low-half-life / high-threshold setting can never collapse to instant deletion.
    forget_min_retention_days: float = Field(default=1.0, ge=0)
    # Per-partition forgetting overrides, keyed by partition id. Operator policy
    # (not data) — lives here in config so it survives DB rebuilds and is editable
    # in hebb.json. Unset numeric fields inherit the region/global defaults; an entry
    # with enabled=false exempts that partition from the forgetting sweep.
    forgetting_overrides: dict[str, PartitionForgettingOverride] = Field(default_factory=dict)

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

    def allowed_origins(self) -> list[str]:
        """Browser origins permitted to call the console/API (CORS + anti-CSRF).

        The web console is served same-origin from this process, so the only
        legitimate browser origins are loopback at the configured port. Requests
        carrying any other ``Origin`` header are cross-site (a drive-by webpage)
        and are rejected by the anti-CSRF guard. Non-browser clients send no
        ``Origin`` header and are unaffected.

        Returns:
            Loopback origins (``127.0.0.1`` and ``localhost``) at ``self.port``.
        """
        return [
            f"http://127.0.0.1:{self.port}",
            f"http://localhost:{self.port}",
        ]
