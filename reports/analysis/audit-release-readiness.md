# Hebb Mind — Open-Source Release Readiness Audit

**Audit date**: 2026-05-15
**Subject**: `hebb-mind` v0.1.1 (PyPI), repo `github.com/afx-team/hebb-mind`
**Scope**: community signals, repo hygiene, CI, release process, metadata
**Benchmarks**: rich, httpx, fastapi, pydantic

---

## TL;DR — Top 8 Issues (by severity)

| # | Severity | Issue |
|---|----------|-------|
| 1 | **Blocker** | No `SECURITY.md` and no `CODE_OF_CONDUCT.md` (GitHub flags both as missing community standards) |
| 2 | **Blocker** | No issue templates and no PR template under `.github/` (only `workflows/` exists) |
| 3 | **Blocker** | `CHANGELOG.md` is stuck at v0.1.0 dated 2026-04-17, but PyPI is at v0.1.1 — release notes never updated |
| 4 | **High** | `CLAUDE.md` is stale: claims "Research & design phase", "VuePress" (project uses **VitePress**), and lists `[ ] Implement core components` as TODO when src/ is fully implemented |
| 5 | **High** | CI matrix only tests Python **3.12 + 3.13**, but `pyproject.toml` declares support for **3.10–3.13** (no proof 3.10/3.11 actually works) |
| 6 | **High** | Repo `.git` is **2.7 GB** because 38 model weight files (2.2 GB on disk) are LFS-tracked into the public repo — `git clone` will pay LFS bandwidth on day one |
| 7 | **High** | No coverage reporting (no codecov upload), no type-check step in CI (mypy is configured `strict = true` but never runs in CI), no docs-build verification on PRs |
| 8 | **Medium** | `LICENSE` says "Copyright (c) 2015-present Ant UED" but pyproject author is `afx-team` — copyright/author mismatch raises licensing questions |

---

## Per-Area Findings

### CI (`.github/workflows/`)

Three workflows present: `ci.yml`, `publish.yml`, `deploy-pages.yml`.

**ci.yml**
- Matrix: `[ubuntu, macos, windows] × [3.12, 3.13]` — **misses 3.10 and 3.11** even though pyproject claims them.
- Runs `ruff check src/` and `pytest tests/ -v` only. **No** `mypy`, **no** `ruff format --check`, **no** coverage upload, **no** docs build dry-run.
- `pip install -e ".[dev]"` with no caching → slow.
- Docker job builds image but never tests/pushes it.
- No concurrency cancellation (PRs queue old builds).

**publish.yml**
- Triggers on every push to `main` that touches `pyproject.toml` — clever, but will silently no-op if version unchanged. A comment explaining this in CONTRIBUTING would help contributors who want to cut releases.
- Uses PyPI Trusted Publisher (good) but **builds without running tests first** — could publish a broken wheel.
- Tag is created **after** publish, not before. Conventional flow is tag-driven release.
- No GitHub Release is created; no release notes attached to the tag.
- No `sdist` + `wheel` provenance attestation (PyPI attestations are an easy win in 2026).

**deploy-pages.yml**
- Solid. Triggers on `repo_pages/**` change. Uses `npm ci`. Uploads to GH Pages. Good.

### Issue / PR Templates

`.github/` contains only `workflows/`. Compared to fastapi/httpx, missing:
- `ISSUE_TEMPLATE/bug_report.yml`
- `ISSUE_TEMPLATE/feature_request.yml`
- `ISSUE_TEMPLATE/config.yml` (links to discussions/security)
- `PULL_REQUEST_TEMPLATE.md`
- `CODEOWNERS` — no review routing
- `FUNDING.yml` — no sponsor button (optional)
- `dependabot.yml` — no automated dep PRs (this is a real risk for an LLM project shipping `litellm`, `fastapi`, `mcp`)

### Community Health Files

| File | Present | Notes |
|------|---------|-------|
| README.md | Yes | Strong; bilingual; competitive comparison table; mermaid arch diagram |
| README_ZH.md | Yes | Bilingual mirror |
| LICENSE | Yes | MIT, but copyright string is wrong |
| CONTRIBUTING.md | Yes | Adequate; missing release-process and DCO/CLA notes |
| CHANGELOG.md | **Stale** | Only v0.1.0; not Keep-a-Changelog format (no `[Unreleased]`, no compare links) |
| CODE_OF_CONDUCT.md | **No** | Should adopt Contributor Covenant 2.1 |
| SECURITY.md | **No** | Required for vulnerability reporting; GitHub will display "Security policy: not enabled" |
| AGENTS.md | Yes | Present (agent contributor guide) |
| CLAUDE.md | Yes | **Stale** — see below |
| LEGAL.md | Yes | Bilingual disclaimer |
| `.gitattributes` | Yes | LFS rules for models/ + eval/data/ |
| `.gitignore` | Yes | Comprehensive — `*.db`, `dist/`, `build/`, `knowledge_graph.json` all ignored |

### README Badges

Currently 5 badges: Docs · CI · PyPI version · MIT license · Python versions. **Missing high-trust signals**:
- `pypi/dm/hebb-mind` (downloads/month — adoption signal)
- `codecov/c/github/afx-team/hebb-mind` (coverage)
- `github/stars/afx-team/hebb-mind` (social proof)
- `github/actions/workflow/status/.../deploy-pages.yml` (docs-build)
- Pre-commit / Ruff badge (modernity signal)
- DOI / Zenodo (if academic citation desired)
- Discord/Slack community link (if a chat exists)

Also: the docs badge points to a static `shields.io/badge` rather than a real status — replace with the live `deploy-pages.yml` status.

### CHANGELOG

- Format is **not** [Keep a Changelog](https://keepachangelog.com): no `[Unreleased]` section, no `### Changed/Fixed/Removed`, no compare links.
- **Last entry: 2026-04-17 v0.1.0**. Since then there have been ~20 commits (CLI doctor/setup/model commands, Codex integration, launchd service, workspace resolution, ingest pipeline, query sanitizer, transcript parsing, MCP-CC integration, daily consolidation time, etc.) and a **PyPI release of v0.1.1** with **no documented changes**. Users cannot see what changed.

### PyPI metadata (`pyproject.toml`)

Strengths: trusted publisher, classifiers cover 3.10–3.13, scripts entrypoints declared, `[pg]` extra defined.

Gaps:
- `Development Status :: 3 - Alpha` — fine, but consider `4 - Beta` once 0.1.x stabilizes.
- Missing classifiers: `Framework :: FastAPI`, `Topic :: Software Development :: Libraries :: Python Modules`, `Operating System :: OS Independent`, `Topic :: Database`, `Typing :: Typed`.
- No `py.typed` marker file in `src/hebb/` (despite `mypy strict = true`) — downstream type users will see `Skipping analyzing 'hebb': module is installed, but missing library stubs or py.typed marker`.
- `project.urls` missing: `Changelog`, `Documentation` (currently points to README anchor — should be the live VitePress site), `Funding`.
- Author email is a noreply address — fine for privacy, but provide a real contact in SECURITY.md.
- `pysqlite3` darwin-only pin is unusual; worth a comment in pyproject explaining why (macOS system sqlite lacks vec extension support).

### Repo Hygiene

- **`.gitignore` is good** — `*.db`, `*.db-shm`, `*.db-wal`, `build/`, `dist/`, `*.egg-info/`, `*.whl`, `knowledge_graph.json`, `hebb.json` all ignored. Verified via `git check-ignore` — none committed.
- **`.git` is 2.7 GB** — driven almost entirely by 38 LFS-tracked model files in `models/` (2.2 GB on disk) and 275 MB of eval data in `eval/data/`. While LFS-tracked, **a fresh `git clone` still downloads LFS objects by default**, surprising users.
  - Recommendation: move `models/` out of the repo entirely — `hebb setup` already downloads from HuggingFace. There is no reason to ship weights.
  - Recommendation: gate `eval/data/` behind a separate repo or document `GIT_LFS_SKIP_SMUDGE=1` in CONTRIBUTING.
- `plan.md` at repo root is gitignored (good) but its presence near the top of `ls` is a code smell — move into `reports/`.
- `hebb.example.json` is committed (good) but `embedding_dim: 384` and `embedding_model: all-MiniLM-L6-v2` contradict the README which says default is `BAAI/bge-large-en-v1.5` / `BAAI/bge-m3` — confusing for first-time readers.

### Security

- No `SECURITY.md` (vulnerability disclosure path).
- No `dependabot.yml` despite shipping `litellm`, `fastapi`, `uvicorn`, `mcp`, `pydantic`, `pyjwt` — all attack surface.
- No automated security scan workflow (CodeQL, `pip-audit`, or `bandit`).
- No SBOM generation in publish flow.
- `PyJWT` is in dependencies, suggesting the project handles OAuth tokens (README confirms GitHub OAuth) — security disclosure path is doubly important.

### CLAUDE.md Staleness

- **L18**: "Type: Research & design phase → Production implementation" — repo is **clearly in production** (PyPI v0.1.1, MCP server, CLI, Docker, docs site).
- **L23–26**: Phase Focus lists `[ ] Implement core components` — done.
- **L34**: "VuePress site" — actual stack is **VitePress** (see `repo_pages/.vitepress/`, `deploy-pages.yml`, `package-lock.json`).
- **L42**: `src/  # Source code (TBD)` — not TBD.
- **L138**: "Multi-Model Support — Design for Codex, GPT, Llama compatibility" — original was likely "Claude" (project supports Claude via LiteLLM). Looks like a search-replace gone wrong.
- **L177**: "VuePress page format" — same VitePress error.
- Missing top-level mention that `src/hebb/` has 9 sub-modules (config, models, storage, embedding, retrieval, graph, agents, scheduler, server, cli, mcp) — refer to CONTRIBUTING for the live tree.

### Pre-commit

- Uses `language: system` for all hooks — requires every contributor to have `ruff`, `pytest`, etc. on PATH. Standard practice is `repo: https://github.com/astral-sh/ruff-pre-commit` (pinned hash) so hooks self-install.
- Runs full `pytest` on every commit — slow; consider only on push, or only changed paths.
- No `ruff format` autofix hook (only `--check`).
- No `pre-commit autoupdate` schedule (use `ci:` block).
- Not registered in CI — pre-commit only runs locally; CI has a separate `ruff check` step.

### Release Process Documentation

- **None.** A new contributor cannot answer: "How do I cut v0.1.2?"
- Implicit flow (inferred from `publish.yml`): bump `pyproject.toml` version → push to `main` → GH Action publishes → tag is auto-created.
- No documented requirement to update `CHANGELOG.md` first. This is why v0.1.1 shipped with no changelog entry.
- No GitHub Release is created — only a bare git tag. Users browsing the Releases page will see nothing.

---

## Don't Ship Without Fixing (Must-Haves)

1. **Add `SECURITY.md`** — vulnerability disclosure email, supported versions table.
2. **Add `CODE_OF_CONDUCT.md`** — Contributor Covenant 2.1 verbatim.
3. **Update `CHANGELOG.md`** — add `[Unreleased]` + 0.1.1 entry covering CLI doctor/setup/model, Codex integration, launchd, workspace, ingest, query sanitizer, transcript, MCP-CC, daily consolidation. Adopt Keep-a-Changelog.
4. **Fix `LICENSE` copyright** — make holder match author (afx-team) or add proper attribution.
5. **Fix CI matrix** — include 3.10 and 3.11 (or drop the classifiers).
6. **Add issue templates** (bug, feature) and a PR template — GitHub will surface these in the new-issue UI.
7. **Add `dependabot.yml`** — weekly pip + github-actions updates.
8. **Rewrite or delete `CLAUDE.md`** — remove "research phase", VuePress, and TBD references; reflect production reality.
9. **Stop shipping model weights in git** — remove `models/` from the repo (let `hebb setup` fetch them); keeps `git clone` fast.
10. **Run tests before publish** — make `publish.yml` depend on `ci.yml` success or duplicate the test step.

## Polish (Nice-to-Haves)

- `CODEOWNERS` for review routing.
- `FUNDING.yml` if sponsorship channel exists.
- Coverage upload to Codecov + badge.
- `mypy --strict` step in CI (config already exists).
- `py.typed` marker in `src/hebb/`.
- Add `Framework :: FastAPI`, `Typing :: Typed`, `Operating System :: OS Independent` classifiers.
- Add `project.urls.Changelog` and point `Documentation` to the live site.
- Replace static docs badge with live deploy-pages status.
- Add downloads/month, stars, codecov, pre-commit badges to README.
- Adopt `astral-sh/ruff-pre-commit` standard hooks (self-installing).
- Document release process in `CONTRIBUTING.md` (or new `RELEASING.md`).
- Auto-create GitHub Release with notes from CHANGELOG on tag push.
- Add CodeQL workflow.
- Add `pip-audit` step in CI.
- Cache pip in CI (`actions/setup-python` already supports `cache: pip`).
- Add concurrency cancellation to `ci.yml`.
- Reconcile `hebb.example.json` with README defaults.
- Move `plan.md` out of repo root into `reports/`.

---

## Concrete File-Level Fix List

| Path | Action |
|------|--------|
| `/Users/xiyue/Projects/alipay/hippocampus/SECURITY.md` | **Create** — disclosure email, supported version table, response SLA |
| `/Users/xiyue/Projects/alipay/hippocampus/CODE_OF_CONDUCT.md` | **Create** — Contributor Covenant 2.1 |
| `/Users/xiyue/Projects/alipay/hippocampus/CHANGELOG.md` | **Rewrite** — Keep-a-Changelog format; add `[Unreleased]` and `[0.1.1]` sections from git log |
| `/Users/xiyue/Projects/alipay/hippocampus/LICENSE` | **Edit** L3 — replace `Ant UED, https://xtech.antfin.com/` with `afx-team contributors` (or appropriate Ant entity confirmed by legal) |
| `/Users/xiyue/Projects/alipay/hippocampus/CLAUDE.md` | **Rewrite** — drop "research phase" framing; correct VuePress→VitePress; remove TBD; fix Codex/Claude search-replace bug L138; reflect implemented modules |
| `/Users/xiyue/Projects/alipay/hippocampus/CONTRIBUTING.md` | **Append** — release-process section: bump version → update CHANGELOG → push to main → publish.yml handles rest |
| `/Users/xiyue/Projects/alipay/hippocampus/pyproject.toml` | **Edit** — add classifiers (`Framework :: FastAPI`, `Typing :: Typed`, `OS Independent`); add `project.urls.Changelog` + real `Documentation` URL |
| `/Users/xiyue/Projects/alipay/hippocampus/src/hebb/py.typed` | **Create** — empty marker file; add to `package-data` in pyproject |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/workflows/ci.yml` | **Edit** — add `3.10`, `3.11` to matrix; add mypy step; add `cache: pip`; add `concurrency:` block; add coverage upload |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/workflows/publish.yml` | **Edit** — depend on CI success; create GitHub Release from CHANGELOG; consider tag-driven trigger |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/dependabot.yml` | **Create** — weekly updates for `pip` + `github-actions` ecosystems |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/ISSUE_TEMPLATE/bug_report.yml` | **Create** — structured form with version/OS/repro |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/ISSUE_TEMPLATE/feature_request.yml` | **Create** |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/ISSUE_TEMPLATE/config.yml` | **Create** — link to Discussions and SECURITY.md |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/PULL_REQUEST_TEMPLATE.md` | **Create** — checklist (tests, changelog, docs, lint) |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/CODEOWNERS` | **Create** — route reviews |
| `/Users/xiyue/Projects/alipay/hippocampus/.github/workflows/codeql.yml` | **Create** — weekly CodeQL scan |
| `/Users/xiyue/Projects/alipay/hippocampus/README.md` | **Edit** — replace static docs badge with workflow status; add downloads/coverage/stars badges |
| `/Users/xiyue/Projects/alipay/hippocampus/README_ZH.md` | **Edit** — mirror README badge changes |
| `/Users/xiyue/Projects/alipay/hippocampus/.pre-commit-config.yaml` | **Replace** — switch to `astral-sh/ruff-pre-commit` upstream hooks; drop pytest from pre-commit (move to pre-push); add `ci:` autoupdate block |
| `/Users/xiyue/Projects/alipay/hippocampus/models/` | **Remove from repo** — let `hebb setup` download; update `.gitattributes` and `.gitignore` |
| `/Users/xiyue/Projects/alipay/hippocampus/hebb.example.json` | **Edit** — align defaults with README (bge-large-en-v1.5, dim 1024) or document why example differs |
| `/Users/xiyue/Projects/alipay/hippocampus/plan.md` | **Move** to `reports/` (currently gitignored but visually noisy) |
| `/Users/xiyue/Projects/alipay/hippocampus/RELEASING.md` (or section in CONTRIBUTING) | **Create** — explicit cut-a-release runbook |
