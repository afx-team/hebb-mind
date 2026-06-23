# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- Maintained MANUALLY (release-please automation removed). On each release:
     1. Add a new "## [x.y.z] - YYYY-MM-DD" section below, grouped by
        Added / Fixed / Performance / Changed / Documentation.
     2. Bump the version in pyproject.toml, src/hebb/__init__.py,
        .release-please-manifest.json, and .claude-plugin/plugin.json.
     3. Merge to main — publish.yml ships to PyPI on the pyproject.toml change
        and tags the release. -->

## [0.2.0] - 2026-06-23

### Added

- **Web console restructure**: the console is reorganized around the four memory
  lifecycle stages — **Manage** (memories / partitions / graph as in-page tabs,
  with overview stats), **Activate** (recall test + retrieval parameters),
  **Consolidate** (trigger + run records + config), and **Forget** (trigger +
  records + global defaults + per-partition tuner) — plus a **System** page for
  infrastructure config (LLM / embedding / storage / server) and the existing
  CC-memory page. Unified design language, deep-linkable tabs (`#page/sub`), and a
  `lifecycle.js` teardown registry that tears down timers/observers on navigation.
- **Forgetting run tracking**: each forgetting sweep (scheduled or manual) is
  recorded with scanned / deleted / partitions-swept counts and surfaced as a
  records panel on the Forget page.

### Changed

- **Forgetting now uses a retention-score model** (a true Ebbinghaus curve)
  instead of the previous dynamic-TTL crossover. Each memory has a retention that
  decays from its last access — `retention(idle) = exp(-idle / eff_half_life)`,
  where `eff_half_life = half_life_days · (1 + k_importance·(importance/10) +
  k_access·(access_count/10))` — and is forgotten once retention drops below
  `threshold`. This is monotonic in importance and access (the old model could
  forget a once-accessed memory *sooner* than a never-accessed one) and uses
  long-term defaults (30–180 day half-lives per cortical region) instead of the
  old day-scale TTLs.
- **BREAKING (config)**: the global `base_ttl_hours` / `decay_factor` settings and
  the per-partition override fields of the same name are **removed**, replaced by
  `half_life_days`, `k_importance`, `k_access`, `forget_threshold`, and
  `forget_min_retention_days` (global) plus `half_life_days` / `k_importance` /
  `k_access` / `threshold` (per-partition override). Legacy keys in `hebb.json` are
  ignored; per-partition overrides fall back to the region/global defaults — re-tune
  in the console's **Forgetting** page if you had custom retention policies.
- **Console — Forgetting page** reworked for the new model: a retention decay curve
  with a threshold line, a contrast-fixed importance×access matrix (access axis now
  0–100), a "how forgetting works" explainer, and the working-memory inbox hidden
  from the partition picker (it is never swept).

## [0.1.8] - 2026-06-09

### Added

- **Consolidation run tracking**: every consolidation run now writes a dedicated
  log file plus a JSON manifest, surfaced as a "Recent runs" history panel in the
  dashboard with live log streaming and per-run status.
- **Interruption recovery**: consolidation runs carry a heartbeat, so a run that
  stalls or is cut off (network loss, shutdown, system sleep) is detected and
  marked `interrupted` instead of getting stuck `running` forever. On the next
  start, if working memories are still pending, a one-shot catch-up consolidation
  is scheduled so the inbox resumes rather than waiting for the daily cron.
- **`consolidation_drain_empty_sources` setting** (Lifecycle tab, default on):
  working memories the consolidator judges low-value (a well-formed empty result)
  are drained from the inbox instead of being re-checked on every run.
- **Virtualenv guard for `hebb service install`**: warns when installing the
  background service from inside a virtualenv (which breaks if the venv is
  removed) and makes the OS service PATH venv-aware.

### Fixed

- **Consolidation no longer loops on empty output**: a robust JSON parser
  (backed by the `json-repair` library) recovers responses some models emit with
  doubled braces (`{{ … }}` under `json_object` mode), truncated at `max_tokens`,
  or with trailing commas — these were previously dropped, silently losing
  consolidated memories and degrading recall query/tag extraction. Genuine
  low-value content is drained; only unparseable/transient failures are kept for
  retry, so the working inbox finally empties.
- **Consolidation race-tightening**: the cron sweep, manual `/consolidate`, and
  the MCP tool now serialize through a single "working" state — duplicate runs
  are deduplicated and the cron skips a tick when a run is already in progress.

### Changed

- Add `json-repair` runtime dependency (MIT, pure-Python, no mandatory
  transitive dependencies).
- Evaluation reports are now pathed under `{benchmark}/{hebb_version}/run-N/`
  (the shipped version that produced a number is legible at a glance); the eval
  methodology version is recorded in the report body instead of the path.

## [0.1.7] - 2026-06-08

### Added

- **Custom HTTP (JSON) embedding API mode** plus more robust local-model cache
  detection, so any JSON embedding endpoint can back retrieval and offline runs
  reuse a cached model without re-downloading.
- **Evaluation harness**: official LongMemEval QA (per-type `get_anscheck_prompt`
  judge + neutral official reader) and a full MemBench 11-category sweep with
  per-category Hit@k.
- **`hebb setup` wizard**: interactive first-run setup with embedding model
  selection (small/base/large) and optional LLM key input; defaults to
  `all-MiniLM-L6-v2` for low-resource environments.
- **`hebb doctor` health-check**: validates config, embedding model readiness,
  and service connectivity in one command.

### Fixed

- **Security: bind `127.0.0.1` by default**, remove wildcard CORS, strip the
  `/api/v1/config/reveal` endpoint, and redact secrets from all config surfaces.
- **Security: path traversal guard** on partition/namespace parameters across
  all storage backends.
- **Atomic writes**: memory creation wraps vector insert + FTS index + graph
  update in a single transaction; partial failures roll back cleanly.
- **Embedding dimension migration** no longer drops the vector table — uses
  `ALTER` or safe rebuild with data preservation.
- **Service install pins `HEBB_HOME`** so background daemons are independent of
  the working directory at install time.
- **Consolidation agent** validates LLM output schema before deleting source
  memories, preventing zero-replacement data loss on malformed responses.
- **Knowledge graph**: entity extraction uses overlap-chunked queries (no more
  whole-query substring matching), and graph recall respects partition filters.
- **Forgetting scheduler**: `importance=0` no longer yields `TTL=0` (instant
  delete); minimum TTL floor enforced.
- **Retrieval**: strict-mode threshold comparison is scale-aware (normalized
  before gating); IDF calibration activated on startup instead of dead code path.
- **Claude Code Stop hook no longer ingests subagent content.** The transcript
  parser now drops `isSidechain` (Task tool) lines, so a subagent's task prompt
  can no longer be stored as the user's turn and its tool calls no longer leak
  into the saved summary.
- **Cross-store delete consistency.** A single `purge_memory` helper keeps the
  SQLite row, vec0 embedding, FTS5 index, and knowledge graph in sync across the
  delete endpoint, the forgetting scheduler, the library facade, and every
  consolidation delete site (consolidation previously stripped rows without
  graph cleanup, orphaning tag nodes). Session consolidation no longer deletes
  its source memories when the LLM returns no usable output — preventing
  zero-replacement data loss.

### Changed

- Default embedding model changed from `all-mpnet-base-v2` (420 MB) to
  `all-MiniLM-L6-v2` (90 MB) — halves first-run download time with <2%
  retrieval quality loss on LoCoMo/MemBench.
- Docker image uses `hebb service start` (not removed `hebb start`).
- Web console settings page redacts API keys (shows last 4 chars only).

### Documentation

- Refreshed benchmark pages (LongMemEval, MemBench) and framework comparisons,
  EN + `zh/` mirrors.
- New-user experience audit report and core system audit report (internal,
  `reports/audit/`).

## [0.1.6] - 2026-06-01

### Fixed

- **Retrieval-induced strengthening ("use it or lose it").** `POST
  /api/v1/search` now bumps `access_count` + `last_accessed_at` on the
  memories it returns (new `update_access_batch` store method), gated by
  the `recall_strengthening_enabled` setting (default on). The dynamic
  forgetting TTL and recency ranking already rewarded access/recency, but
  nothing on the search path fed them — only `GET /memories/{id}` did — so
  frequently-recalled memories decayed as if never used. In-process recall
  during consolidation bypasses this; benchmarks disable it for snapshot
  reproducibility.
- **Session / turn metadata fidelity.** The Claude Code Stop hook now
  stamps `metadata.turn` (counting human turns, skipping tool_result
  carriers); session consolidation preserves the source turns' `turn_pair`
  span and earliest `timestamp` on its output instead of emitting a bare
  `session_id`; conversation ingestion preserves each turn's `timestamp`.
  Together these restore turn-window expansion and `temporal_boost` on
  consolidated and ingested memories.

### Added

- **Per-scenario consolidation.** `consolidate_batch` /
  `run_consolidation` gain `source_partition` and `keep_partition` so a
  partition can be consolidated in place (writing back to itself, skipping
  cross-partition recall) — required for partition-scoped evaluation
  benchmarks (LongMemEval / ConvoMem).
- **LLM client robustness.** Per-request timeout (120s) and automatic
  retries on transient provider failures, so a single stalled response
  can no longer deadlock a long consolidation batch.

## [0.1.5] - 2026-05-31

### Added

- **Retrieval: calibrated keyword channel + blend re-rank.** The keyword
  channel is blend re-ranked (BM25 magnitude × query-term coverage /
  proximity) to lift its intrinsic top-1, and feeds Reciprocal Rank Fusion
  a better-ordered list; its similarity is calibrated to `[0, 1]` and
  decoupled from RRF rank (and an inverted SQLite keyword-similarity sign
  was fixed). Improves standalone keyword retrieval without depending on
  the cross-encoder reranker.
- **Retrieval: vector-search toggle.** The vector retrieval channel can be
  disabled via the `vector_search_enabled` setting (and the corresponding
  CLI/console control), for keyword-only deployments and channel ablation.

## [0.1.4] - 2026-05-29

Maintenance release. No changes to the published Python package (`src/`
and dependencies are unchanged from 0.1.3); this version bump covers
documentation-site, evaluation-harness, and CI updates and was cut
manually because the release-please Release PR could not be opened
(GitHub Actions lacked permission to create pull requests).

### Changed

- **Docs site.** Home-page background video and navbar visibility,
  responsive-layout fixes (removed scroll-snap), new Simplified-Chinese
  benchmark pages (LoCoMo, PersonaMem) and updated quick-start links.
- **Eval harness.** Updated PersonaMem accuracy numbers and LoCoMo
  rank-matrix reports.
- **CI.** Enabled Git LFS in the docs checkout step; added repository
  link to the docs-site `package.json`.

## [0.1.2] - 2026-05-26

### Added

- **Retrieval: turn-window context expansion.** `POST /api/v1/search` now
  accepts `prev_turns` and `next_turns` (both default `0`). For memories
  written with `metadata.session_id` + `metadata.turn`, the searcher
  surfaces the requested number of adjacent same-session turns in
  `related`, deduplicated across hits. This is what production Claude
  Code uses by default (2/2 window) and is responsible for several
  percentage points of the LoCoMo R@10 number.
- **Retrieval: date-proximity boost.** New `src/hebb/retrieval/temporal_boost.py`
  parses absolute (`August 2023`, `7 May 2023`, `in 2022`) and relative
  (`last week`, `3 days ago`, `yesterday`) date anchors from queries and
  multiplicatively boosts candidate memories whose `metadata.timestamp`
  falls inside the tolerance window (up to +40%, decaying past 3×
  tolerance). Reference for relative phrases is `today` by default.
- **Retrieval: FTS5 query sanitiser + porter stemming + synonym groups.**
  New `src/hebb/retrieval/fts_query.py` normalises LLM-generated queries
  into safe MATCH expressions (strips punctuation, drops stopwords,
  emits CJK bigrams, expands ~28 deliberately-general English synonym
  groups: `kid/child`, `buy/purchase`, etc.). `migrations.py` now creates
  the FTS5 table with `porter unicode61` so morphological variants
  (`researched` ↔ `research`) match without per-term expansion.
- **Storage: turn-neighbour fetch.** `MemoryStore.get_turn_neighbors()`
  on both `SqliteStore` and `PgStore` for the turn-window expansion path.
- **Claude Code hook: timestamp prefix.** `integrations/claude_code/transcript.py`
  prepends `[<ISO timestamp>]` to every turn-summary memory so the
  downstream LLM can resolve relative-time queries from retrieved text
  alone, not just metadata.
- **Eval: production-mirror LoCoMo benchmark + session-level R@k.**
  `eval/benchmarks/locomo_bench.py` ingests via the *same* hook code
  paths that ship to production (per-utterance + per-turn-pair, no
  chunking, no image captions) and scores by MemPalace-style session
  evidence recall. New `eval_version` field on each benchmark class
  isolates protocol versions in the report tree
  (`eval/reports/{benchmark}/{eval_version}/run-{N}/`) — no more
  date-keyed directories.
- **OS-managed background service is now the only supported way to run
  Hebb Mind.** `hebb service install` registers the server with launchd
  (macOS), systemd (Linux), or Task Scheduler (Windows) and starts it.
  Defaults to `--scope user` — no admin or sudo. `--scope system` is the
  opt-in elevated path. New subcommands: `hebb service {install,uninstall,
  start,stop,restart}`. Internal foreground entrypoint is the hidden
  `hebb _serve` command, invoked only by the service manager.
- **`hebb console`** — open the Web Console in your default browser with one
  command. `--print` outputs the URL only (CI / SSH friendly).
- `hebb doctor` now reports the OS service registration state alongside
  the HTTP health check.
- Community health files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue and pull
  request templates under `.github/`, `CODEOWNERS`, and a `dependabot.yml`
  config covering `pip` and `github-actions`.

### Changed

- **LoCoMo benchmark headline numbers (full 1,978q, session-level R@10):**
  **93.3% bge-large-1024** / **89.7% MiniLM-384** — at both embedding
  tiers ~+0.9 pp over MemPalace's published same-embedding pipelines
  (92.4% / 88.9%). The previously-published 92.7% number was based on a
  3-scenario / 494q slice and has been retired in favour of these
  full-coverage figures. Headline runs preserved at
  `eval/reports/locomo/v3/run-{1,2}/`.
- `/api/v1/admin/consolidate` now returns per-batch error details on
  partial failure instead of a single boolean.
- `POST /api/v1/config` synchronises the live `Settings` singleton so
  field updates take effect without a server restart, and returns the
  coerced value.

### Removed

- **Breaking:** `hebb start`, `hebb stop`, `hebb restart`, the
  `--daemon` flag, and the workspace `hebb.pid` file. Use the new
  `hebb service` subcommands instead. The MCP server and Claude Code
  hooks now ask the OS service manager to start the server on demand.
- **Breaking:** CLI surface cleanup. No backwards-compatible aliases.
  - `hebb init` removed — `hebb setup` already creates the workspace on
    first run.
  - `hebb workspace` removed — use `hebb config get workspace`.
  - `hebb service status` removed — merged into top-level `hebb status`,
    which now shows OS service registration, HTTP health, and scheduler
    jobs in a single view.
  - `hebb cc <subcommand>` renamed to `hebb claude-code <subcommand>` for
    parity with `hebb codex`. Existing Claude Code installations must
    re-run `hebb claude-code install --scope user` (or `project`) so the
    settings.json hook commands point at the new name; the uninstaller
    still recognises the legacy `cc` pattern so cleanup works either way.
  - `hebb mcp` is now a group; the stdio server is started via
    `hebb mcp serve`. MCP client configs that point at the `hebb-mcp`
    console-script entry point are unaffected.
- CI: `mypy --strict` step, `actions/setup-python` pip caching, coverage
  uploaded as a workflow artifact, separate docs-build verification job that
  runs on PRs touching `repo_pages/**`, and workflow-level concurrency
  cancellation.

### Changed

- **Project renamed `hippocampus` → Hebb Mind.** The name honors Canadian
  neuropsychologist Donald O. Hebb and his learning rule — *neurons that fire
  together, wire together*. This is a **breaking change**:
  - PyPI package `afx-hippocampus` → `hebb-mind`; install with `pip install hebb-mind`.
  - CLI command `hippocampus` → `hebb`; MCP entry point `hippocampus-mcp` → `hebb-mcp`.
  - Python import `hippocampus` → `hebb`; public facade class `Hippocampus` → `HebbMind`;
    base exception `HippocampusError` → `HebbMindError`.
  - Config file `hippocampus.json` → `hebb.json`; workspace dir `~/.hippocampus/` →
    `~/.hebb/`; environment variables `HIPPOCAMPUS_*` → `HEBB_*`.
  - The MCP server registers as `hebb`.
  - "hippocampus" is retained **only** as the name of the working-memory partition
    (`mem_hippocampus`) — the inbox where new memories land before consolidation.
- `publish.yml` now runs the test matrix (lint + mypy + pytest on Python
  3.10 – 3.13) before building and uploading to PyPI, so a broken `main` can
  no longer ship a release.
- CI test matrix expanded to cover Python 3.10, 3.11, 3.12, and 3.13 to match
  the versions advertised in `pyproject.toml`.
- `CHANGELOG.md` rewritten to follow the Keep a Changelog format.

## [0.1.1] - 2026-05-12

### Added

- **CLI**: `hebb doctor`, `hebb model`, and `hebb setup`
  commands for installation health checks, embedding-model selection, and
  guided initialisation.
- **Embedding catalog**: language- and region-aware model selection so
  English, Chinese, and multilingual deployments pick sensible defaults.
- **Codex integration**: install / uninstall commands for registering
  Hebb Mind as an MCP server in Codex CLI environments.
- **Claude Code integration**: MCP service hooks for memory management,
  including ingest and consolidation triggers.
- **Conversation ingest pipeline**: `POST /api/v1/ingest/conversation`
  endpoint, transcript parsing, turn-summary extraction, conversation
  normalisation, and noise stripping.
- **Query sanitiser**: cleans up LLM-generated retrieval queries before they
  hit the vector index.
- **Workspace resolution**: configuration-driven workspace discovery so
  multiple projects can share or isolate memory state.
- **System service management**: launchd integration for auto-start on macOS
  with installation tests.
- **Daily consolidation schedule**: consolidation interval is now expressed
  as a daily wall-clock time instead of a raw interval.
- **Legal disclaimer**: bilingual `LEGAL.md` covering data usage and project
  limitations.

### Changed

- `delete_expired` now returns the IDs of removed memories and prunes the
  associated tag-graph edges.
- `stop` no longer triggers a final consolidation pass; cleanup logic is
  simpler and faster.
- Storage layer recreates the embedding table when the embedding dimension
  changes, so swapping embedding models no longer corrupts the index.
- Datetime handling switched to timezone-aware UTC throughout.
- Default Python requirement lowered to 3.10.

### Fixed

- Embedding-table dimension mismatches when switching models.
- Copy-button visibility on the documentation site.
- Various README and doc link fixes.

## [0.1.0] - 2026-04-17

Initial release.

### Added

- **Memory partitions** — five brain-inspired partitions (hippocampus,
  semantic, episodic, preference, procedural) plus user-defined partitions.
- **Memory consolidation** — LLM-powered agent that processes working memory
  into long-term partitions via Agentic RAG.
- **Dynamic forgetting** — exponential-decay TTL based on access frequency
  and importance.
- **Knowledge graph** — tag-based graph with co-occurrence edges, backed by
  NetworkX + JSON.
- **Storage backends** — SQLite + sqlite-vec (default), PostgreSQL +
  pgvector (optional).
- **REST API** — full CRUD for memories and partitions, search, graph
  queries, and admin endpoints.
- **GitHub OAuth** — optional multi-user authentication (single-user local
  mode by default).
- **CLI** — `hebb init`, `hebb start`, `hebb status`.
- **Docker** — Dockerfile and docker-compose for one-command deployment.
- **Installer** — `curl | sh` with interactive backend selection.
- **Multi-model support** — OpenAI, Anthropic, Qwen, GLM, and Kimi via
  LiteLLM.

[Unreleased]: https://github.com/afx-team/hebb-mind/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/afx-team/hebb-mind/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/afx-team/hebb-mind/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/afx-team/hebb-mind/releases/tag/v0.1.0
