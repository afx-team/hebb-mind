# OSS Launch Readiness — Synthesis & Plan

**Date**: 2026-05-15
**Inputs**: 5 parallel audits in `reports/analysis/audit-{ux-onboarding,architecture,docs-site,examples,release-readiness}.md`
**Goal**: Make `hebb-mind` look polished and trustworthy enough to be popular on day one of public release.

---

## Problem

The codebase is far more mature than the surface signals (CLAUDE.md, CHANGELOG, README) suggest. A first-time visitor in 2026 lands on:

- A v0.1.0 changelog for a v0.1.1 package, with ~20 unreleased commits worth of features hidden.
- A README that promises "Built-in Web Console" and "MCP server" with **zero screenshots**.
- A Quick Start that silently no-ops half its features when the user has no LLM key.
- API docs that document endpoints at `/api/v1/config/*` while the code mounts them at `/api/v1/admin/config/*`.
- A LICENSE with the wrong copyright holder.
- A CI matrix that lies about which Python versions are tested.
- No SECURITY.md, no CODE_OF_CONDUCT.md, no issue/PR templates → GitHub flags missing community standards.
- A latent crash in the embedding factory (`get_embedding_dimension` does not exist on `SentenceTransformer`).
- A 2.2 GB LFS-tracked model directory in the public repo even though `setup` downloads on demand.
- An `examples/` directory that does not exist.

Each issue is small. Together they say "abandoned alpha" — exactly the impression we cannot afford.

## Solution

Six parallel workstreams covering the items where the cost is hours and the impact on first impressions is large. Two destructive items (LFS weight removal, `.git` history rewrite) are flagged for explicit user approval and deferred from this push.

### Stream priorities

| # | Stream | Why first | Files touched |
|---|--------|-----------|---------------|
| **A** | Correctness & cleanup | A latent crash and wrong copyright are credibility-killers. | `LICENSE`, `CLAUDE.md`, `repo_pages/api/*`, `repo_pages/concepts/*`, `repo_pages/advanced/*`, `repo_pages/zh/...`, `src/hebb/embedding/local.py`, `.gitignore`, stale egg-info |
| **B** | README & landing polish | First 30 seconds decide everything. Honest Quick Start, surfaced benchmark, screenshot/GIF placeholders. | `README.md`, `README_ZH.md`, `repo_pages/index.md`, `repo_pages/quick-start.md` (+ZH) |
| **C** | Community health & CI | Removes the "missing community standards" GitHub flag, makes CI honest. | `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS`, `.github/dependabot.yml`, `.github/workflows/*.yml`, `CHANGELOG.md` |
| **D** | Public Python facade | Library users currently have to hand-wire 6 submodules. A `HebbMind()` entry point unlocks the SDK story. | `src/hebb/__init__.py`, `src/hebb/api.py` (new), `src/hebb/exceptions.py` (new) |
| **E** | Examples directory | "No examples" reads as "no users." Ship a runnable Python SDK demo + persistent-chat + benchmark report. | `examples/` (new) |
| **F** | New documentation pages | Troubleshooting / FAQ / benchmarks / migration / web-console pages are table stakes. | `repo_pages/troubleshooting.md`, `repo_pages/faq.md`, `repo_pages/benchmarks.md`, `repo_pages/guide/migration.md`, `repo_pages/guide/web-console.md`, `repo_pages/.vitepress/config.*` |

### Explicitly deferred (need user approval)

- **Repo size** — LFS-tracked model weights (`models/` ≈ 2.2 GB) and 2.7 GB `.git` history. Cleaning these is destructive (force-push, history rewrite). Documented as a follow-up issue, not done in this push.
- **Security hardening** — `allow_origins=["*"]`, settings reload on every `/config` request, JWT auth posture. Behavior-changing; needs a design discussion with the user.
- **Storage refactors** — pagination breakage with tag filter, score normalization across SQLite/PG, forgetting-job O(n) rewrites. Needs proper design — not bundled into a launch-prep push.
- **Dedupe pass** — three `is_server_running` impls, 90% copy-paste in `consolidation_agent.py`. Cleanup PRs after launch.
- **Visual assets** — actual screenshots/GIFs of the Web Console and an asciinema cast. Requires a running browser and the user. Stream B leaves marked placeholders + caption text.

## Trade-offs

- **Breadth over depth**: this push touches ~40 files across 6 streams rather than rewriting any single subsystem. Rationale: the launch impression is bottlenecked by *the worst signal*, not the best. One unprofessional file (stale CHANGELOG) drowns out polished code.
- **No behavior changes in `src/`** beyond fixing the latent embedding crash and adding a public facade module that wraps existing internals. This keeps the diff reviewable and avoids regressions on the eve of a release.
- **EN-first for new doc pages**, with ZH stubs that say "translation in progress." Better than out-of-date ZH that contradicts EN.

## Implementation Plan

Six implementation agents launched in parallel, each with disjoint file ownership (no edit conflicts). Each agent is briefed with the relevant audit report and a tight scope so the work is reviewable.

After agents return, this document gets a "Done / Deferred" appendix and the user gets a one-page summary of what changed.

---

## Appendix A — Done (2026-05-15)

All six streams executed in parallel. 57 files changed/added in the working tree (uncommitted). 13 new facade tests pass.

### Stream A — Correctness & cleanup
- `LICENSE`: copyright corrected to `afx-team contributors`.
- `CLAUDE.md`: rewritten to reflect production state (subsequently re-tightened by user; left as-is).
- `src/hebb/embedding/local.py`: confirmed already uses correct `get_sentence_embedding_dimension()`. Note: `sentence-transformers` v3 deprecated this in favor of `get_embedding_dimension`; pytest warns. Follow-up: switch to the new name once we drop pre-v3 support.
- `repo_pages/api/{admin,cli,config,memories,search}.md` and ZH mirror: drift fixes (admin path prefix, pagination params, response shapes, CLI cut-and-paste bug, full coverage of all 14 commands).
- `repo_pages/concepts/memory-lifecycle.md` (+ZH `consolidation.md`, `forgetting.md`): hourly-vs-daily contradiction resolved to "daily 18:00".
- `repo_pages/advanced/storage-backends.md` (+ZH): truncated `pg-data:` and duplicated heading fixed.
- Stale egg-info dirs: confirmed *not* tracked; `.gitignore` already covers them. No-op.

### Stream B — README & landing
- `README.md` 13.4 KB → 9.1 KB; `README_ZH.md` parity at 9.1 KB.
- New 10-second hero, two-path Quick Start (60-second offline / 5-minute LLM), "Why Hebb Mind" section, real LoCoMo benchmark numbers, trimmed/honest comparison table, two `<img>` placeholders for screenshots.
- `repo_pages/index.md`, `quick-start.md`, and ZH equivalents: brought in line with README.

### Stream C — Community health & CI
- New: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/CODEOWNERS`, `.github/dependabot.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/{bug_report,feature_request,question,config}.yml`, `.github/workflows/docs-pr.yml`.
- `.github/workflows/ci.yml`: matrix expanded to 3.10–3.13, mypy step, pip cache, coverage artifact, concurrency cancel-in-progress.
- `.github/workflows/publish.yml`: gated on a new `test` job so a broken `main` cannot ship to PyPI.
- `CHANGELOG.md`: rewritten in Keep-a-Changelog 1.1.0 format with `[Unreleased]`, `[0.1.1]`, `[0.1.0]`, and link references.
- `CONTRIBUTING.md`: appended security-reporting pointer + 5-bullet release process.

### Stream D — Public Python facade
- New: `src/hebb/api.py` (sync `HebbMind` class, owns a private background event loop), `src/hebb/exceptions.py` (6-class hierarchy), `tests/test_facade.py` (13 tests, all pass).
- `src/hebb/__init__.py`: bumped `__version__` to `0.1.1`, lazy `__getattr__` exports for `HebbMind` + exceptions.
- `pyproject.toml`: registered the `slow` pytest marker and added a mypy override that relaxes `disallow_untyped_decorators` for the `tests/*` tree (so pytest-decorated tests don't trip mypy strict).

### Stream E — Examples
- New `examples/` directory with `README.md`, `01_python_sdk_basics.py`, `02_persistent_chat.py`, `03_mcp_quickstart.md`, `04_benchmarks_locomo.md`, `05_langchain_adapter.py`, `.env.example`.
- All Python files parse; consume the Stream D facade.

### Stream F — Documentation pages
- New EN pages: `repo_pages/troubleshooting.md`, `repo_pages/faq.md`, `repo_pages/benchmarks.md`, `repo_pages/guide/migration.md`, `repo_pages/guide/web-console.md`. Two mermaid diagrams added (benchmarks + web console).
- ZH stubs created for each (translation-in-progress pointer).
- `repo_pages/.vitepress/config.mts`: navbar (+Benchmarks +FAQ) and sidebar (Resources group + new Guide entries) wired for both locales without disturbing existing entries.

### Audit reports retained for reference
- `reports/analysis/audit-{ux-onboarding,architecture,docs-site,examples,release-readiness}.md`
- `reports/design/oss-launch-readiness-plan.md` (this file)

---

## Appendix B — Deferred (need user decision)

| Item | Why deferred | Trigger |
|------|--------------|---------|
| Strip `models/` (≈2.2 GB) from LFS / `.git` history rewrite (≈2.7 GB → ≈100 MB) | Destructive (force-push); mid-flight contributors lose access to historical refs. | One-shot prep before public visibility flip. |
| CORS lockdown (`allow_origins=["*"]`), settings reload on every `/config` request, JWT auth posture | Behavior-changing security hardening — needs design discussion. | Pre-1.0 hardening pass. |
| Storage refactors: tag-filter pagination break, score-normalization parity SQLite/PG, O(n) forgetting-job rewrite | Touches hot paths; needs proper RFC. | After v0.2 plan. |
| Dedupe `is_server_running` (3 copies); collapse 90% copy-paste in `consolidation_agent.py` | Pure cleanup; better as a tagged-up first-issue label for new contributors. | After v0.2 launch. |
| Real screenshots/GIFs (`web-console-hero.png`, `quickstart-cast.gif`, `console-list.png`, `console-graph.png`) | Requires running server + browser + asciinema in a real environment. Placeholders are wired. | One asset push session. |
| Stale `dist/` wheels at 0.1.0 | Untracked; safe to `rm -rf dist/` locally before next build. Confirm before deleting. | Anytime. |
| Adopting the new exception hierarchy across `src/` | Out of scope for "launch readiness" — retrofit PRs after launch. | Iterative. |


