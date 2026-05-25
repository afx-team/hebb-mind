# UX & Onboarding Audit — Hebb Mind

**Audited**: 2026-05-15
**Scope**: First-5-minute experience for an open-source visitor — README, CLI surface, first-run flow, error UX, Web Console.
**Verdict**: Good *bones* (clean CLI tree, neuroscience pitch is differentiated, Web Console exists), but several rough edges will lose users in the first 5 minutes. None are architectural; most are <1h fixes.

---

## TL;DR — Top Friction Points

1. **HIGH** — Zero screenshots/GIFs anywhere in the repo. README, docs site, and `repo_pages/public/` contain only `logo.svg`. A "Built-in Web Console" claim with no visual proof is the single biggest "why should I trust this?" gap. (`README.md:48`, `repo_pages/index.md:34`)
2. **HIGH** — `hebb status`, `hebb stop`, and even `hebb start`'s readiness probe spew raw 50-line `httpx`/`httpcore` tracebacks when the host is unreachable, behind a proxy, or returns a non-JSON body. (`src/hebb/cli/commands/status.py:25-29`, `src/hebb/cli/commands/start.py:45-53`)
3. **HIGH** — README "Quick Start" claims `hebb setup && hebb start` is enough, but the README never tells the user that **consolidation silently does nothing without `llm_api_key`**. The advertised `POST /api/v1/admin/consolidate` endpoint returns `{"processed": 0, ...}` with no warning. (`README.md:69-72`, `src/hebb/server/routers/admin.py:25-44`)
4. **MED** — No "delete all my data" / reset command. `hebb init --force` exists but is not surfaced in `--help` output or docs as a reset path; there is no `hebb reset`. (`src/hebb/cli/commands/init.py:94-95`)
5. **MED** — `hebb.example.json` contradicts what `setup` actually writes (different `embedding_model`, missing 12 keys), and CHANGELOG.md is frozen at v0.1.0 (`hebb init`, `hebb start`, `hebb status` only) while the real CLI now exposes 14 top-level commands. Sloppy signaling = "is this project maintained?" (`hebb.example.json`, `CHANGELOG.md:1-19`)

---

## 1. README.md / README_ZH.md

### What works
- Clear neuroscience hook in the first sentence (`README.md:17`).
- Comparison table vs. Mem0/Letta/Zep is genuinely useful (`README.md:44-52`).
- Mermaid architecture diagram (`README.md:177-222`) is concrete and well-scoped.
- Bilingual coverage; ZH README is a faithful mirror, not a stub.

### Findings

**F1.1 — No screenshots or GIFs (HIGH)**
- **What**: Search across `README.md`, `README_ZH.md`, `repo_pages/`, `repo_pages/public/` finds zero PNG/JPG/GIF/WebP. Only `logo.svg` exists.
- **Why it matters**: The pitch leans on "Built-in Web Console" and "graph visualization" (`README.md:48,62`, `repo_pages/index.md:34`) but a first-time visitor cannot see what they are getting. Mem0, Letta, Zep all have hero screenshots. Without one, the project looks unfinished.
- **Fix**: Add 3 images to `repo_pages/public/screenshots/`: (a) Web Console dashboard, (b) graph view, (c) terminal `hebb setup` output. Embed the dashboard one above "Background & Motivation" in both READMEs. <30 min.

**F1.2 — Quick Start hides the LLM-key gotcha (HIGH)**
- **What**: `README.md:68-72` says three lines get you running. True for ingest + vector search. **False for consolidation, conflict resolution, tag extraction** — all the "agentic" features the README is selling. `llm_api_key` is mentioned only in the Configuration table at line 256, far below the fold.
- **Why it matters**: Users will hit `POST /api/v1/admin/consolidate`, see `"succeeded": 0`, and conclude the framework is broken. The doctor command warns ("`Not configured. Consolidation is disabled until llm_api_key is set.`" at `doctor.py:57`), but only if the user thinks to run it.
- **Fix**: Add a 2-line callout under Quick Start: "Vector search and CRUD work out of the box. To enable consolidation, set `hebb config set llm_api_key sk-...`". Mirror in `repo_pages/quick-start.md:34`.

**F1.3 — Hero pitch buries the differentiator (MED)**
- **What**: The first 10-second read says "brain-like memory system" + "consolidates" — but does not say *what the developer gets*: a single-binary local server with REST + MCP. Compare to "redis but for agent memory" or "LiteLLM for memory" framings.
- **Fix**: One-liner sub-tagline like "Drop-in REST + MCP memory server. SQLite by default, no API key required to start." Above the table of contents.

**F1.4 — `embedding_model` "language-aware" is opaque (LOW)**
- `README.md:260` says "language-aware" with no explanation of how detection works in TOC scanners. Move the one-line explanation up (`setup` reads OS locale).

---

## 2. CLI Surface

`hebb --help` lists 14 commands. Tree is clean and intuitive. Help texts are mostly one-liners (good).

### Findings

**F2.1 — `setup --help` is bare (MED)**
- **What**: `hebb setup --help` output:
  ```
  Options:
    --language [auto|en|zh|multi]  [default: auto]
    --region [auto|cn|global]      [default: auto]
    --profile [default|fast|best]  [default: default]
  ```
  No `help=` strings on any option (`src/hebb/cli/commands/setup.py:28-30`). User has no idea what `profile` does, what `multi` means, or that `--region cn` switches to `hf-mirror.com`.
- **Fix**: Add `help="..."` to each `@click.option`. 5 minutes.

**F2.2 — No `reset` / `delete all` command (HIGH for trust)**
- **What**: There is no `hebb reset`, `hebb uninstall`, or `hebb data wipe`. `init --force` exists (`init.py:94`) but its docstring just says "Overwrite existing config" — users will not guess that it also wipes the SQLite DB and KG.
- **Why it matters**: First-time users want a clean escape hatch ("if I mess up, how do I start over?"). Privacy-conscious users want a guaranteed delete. The absence makes the tool feel sticky in a bad way.
- **Fix**: Either (a) add explicit `hebb reset` (drops db, kg, config; confirms first), or (b) document `init --force` clearly and add `--reset-data` flag. <30 min.

**F2.3 — `cc` and `codex` command names are non-obvious (MED)**
- **What**: `hebb cc install` looks like a typo. Users coming from the README will find `hebb cc install --scope user` (`README.md:93`) without context. `cc` is added with no group docstring exposed to top-level help.
- **Fix**: Either rename to `hebb claude install` / `hebb codex install`, or improve the top-level `--help` description to read e.g. "Claude Code integration (alias: cc)".

**F2.4 — `hebb mcp` is misleading (MED)**
- **What**: `mcp_cmd.py:10-14` says "Requires the hebb service to be running". So `hebb mcp` is a stdio MCP client that proxies to the HTTP server. That is a confusing layering for an MCP server.
- **Fix**: Either embed a self-contained mode, or rename to `hebb mcp proxy` and document the dependency in the help text more visibly.

**F2.5 — `service install` on Linux assumes systemd + sudo, no fallback (LOW)**
- `service.py:113-119` errors out on non-Linux/Darwin. Add a clear error: "Service installation is supported on Linux (systemd) and macOS (launchd) only. For other systems, run `hebb start -d` and use a process supervisor."

---

## 3. First-Run Experience

`hebb init` on a fresh directory produces a clean, friendly output (verified against `/tmp/hippo-test-fresh`).

### Findings

**F3.1 — `init` writes legacy `embedding_model: all-MiniLM-L6-v2` (HIGH)**
- **What**: A fresh `hebb init` writes `"embedding_model": "all-MiniLM-L6-v2"` (verified in `/tmp/hippo-test-fresh/hebb.json`). But `hebb setup` then overrides it to `BAAI/bge-large-en-v1.5` or `BAAI/bge-m3` (`setup.py:96-101`, `embedding/catalog.py:LEGACY_DEFAULT_MODELS`). If a user runs `init` then `start` (skipping `setup`), they get a model the project considers "legacy".
- **Why it matters**: README's Quick Start says `setup && start`, but the docs site quick-start (`repo_pages/quick-start.md:14-32`) and `init`'s own "Next steps" both present `setup` as optional ("Or start directly..." `init.py:131-133`). Following the latter path silently picks a worse model.
- **Fix**: Either (a) make `init` not write `embedding_model` and have `start` fail loudly with "run `hebb setup` first", or (b) remove the "Or start directly" advice from `init.py:131-133`.

**F3.2 — `setup` requires network access on first run with no offline fallback (MED)**
- **What**: `setup.py:67-73` calls `prefetch_model` and verifies. If the user is offline (or HuggingFace is throttled and `--region cn` was not picked), the entire setup fails with a `ClickException`. There is no "skip download, configure later" path.
- **Fix**: Add `--skip-model-download` flag, or catch network errors and print: "Model download failed. Run `hebb model prefetch` later, or set `embedding_enabled=false`."

**F3.3 — `setup` next-steps mention `cc install` and `codex install` even if neither CLI exists (LOW)**
- `setup.py:79-81` recommends both unconditionally. Mirror the doctor pattern: skip recommendations for tools that aren't installed.

**F3.4 — Workspace location is unclear without running `hebb workspace` (LOW)**
- After `setup`, the user is told "Hebb Mind setup complete." but not *where* the workspace lives. `init` does print this; `setup` does not. Add the line.

---

## 4. Error Messages

I tested 4 likely-to-fail commands. Three of them dump full Python tracebacks to the user.

### Findings

**F4.1 — `hebb status --url <unreachable>` dumps a 50-line traceback (HIGH)**
- **What**: `status.py:25-29` only catches `httpx.ConnectError, httpx.RemoteProtocolError`. When the URL is reachable but returns non-JSON (e.g. a corporate proxy interstitial), `httpx.get(...).json()` raises `JSONDecodeError`. When it times out, raises `ReadTimeout`. Both unhandled. Verified.
- **Fix**: Wrap with broad `except (httpx.HTTPError, ValueError) as e` and print one-line: "Cannot reach {url}: {type(e).__name__}".

**F4.2 — `hebb start` itself crashes when the readiness probe hits a proxy (HIGH)**
- **What**: `start.py:45-53` has the same narrow `except`. Verified that running `hebb start --port 19999` in a shell with `HTTPS_PROXY` set produced `httpx.ReadTimeout` traceback **before the server even started**, leaving the user with no idea what happened.
- **Fix**: Use `httpx.get(..., trust_env=False)` for the local readiness probe, or broaden the exception list.

**F4.3 — `hebb stop` when no server is running prints OK, but the underlying detection swallows non-running cases inconsistently (LOW)**
- `stop.py:24-38` does the right thing when truly disconnected (clean message + clean PID file), but the same code paths in `status` do not — inconsistent UX between sibling commands.

**F4.4 — Port-in-use error is unhandled by `start` (MED)**
- **What**: `start.py:145-151` calls `uvicorn.run(...)` directly. If port 8321 is held by another process **that doesn't speak HTTP** (so the readiness probe at `start.py:69` returns False), uvicorn will crash with `[Errno 48] Address already in use` and a stack trace.
- **Fix**: Catch `OSError` around `uvicorn.run` and print: "Port {port} is in use. Try `hebb start --port 8322` or `hebb stop`."

**F4.5 — `config set` exposes raw Pydantic validation messages (LOW)**
- `hebb config set port abc` prints:
  ```
  1 validation error for Settings
  port
    Input should be a valid integer, ...
    For further information visit https://errors.pydantic.dev/...
  ```
  Functional, but ugly. Fix: format `ValidationError` to "Invalid value for `port`: expected integer, got 'abc'." (`config.py:109-111`)

**F4.6 — `config list` shows `home: null` confusingly alongside `workspace: <path>` (LOW)**
- The `home` field is the override, `workspace` is the resolved path. Without docs, this is confusing. Add a `[dim]# override; null = auto[/]` annotation or hide `home` when null.

**F4.7 — Consolidation without LLM key is a silent no-op (HIGH)**
- **What**: `POST /api/v1/admin/consolidate` returns `{"processed": 0, "succeeded": 0, "failed": 0}` when no API key. No HTTP error, no warning. The CLI doctor warns, but the API does not.
- **Fix**: Add a guard in `admin.py:25-44`: if `not settings.llm_api_key`, return HTTP 503 with `{"error": "consolidation_disabled", "reason": "llm_api_key not configured", "fix": "hebb config set llm_api_key ..."}`.

---

## 5. Web Console (First Impression)

The SPA exists at `src/hebb/static/index.html`, has a sidebar with Dashboard / Memories / Search / Partitions / Graph / Settings, dark/light theme toggle, and EN/ZH switcher. Nice surface area. But:

### Findings

**F5.1 — Nothing tells a new user the Web Console exists (MED)**
- README mentions it once at line 74; the docs landing page (`repo_pages/index.md:32-34`) lists it as a feature card but never shows it. No screenshot, no GIF, no demo URL.
- **Fix**: Add screenshot. (Same fix as F1.1.) Optionally host a demo on a small VPS.

**F5.2 — No empty-state guidance in the SPA (MED — needs verification by running it)**
- Based on `index.html`, the sidebar nav is always populated, but there is no visible "Welcome — store your first memory" empty state in the markup. A first-time user with zero memories likely sees a blank Dashboard.
- **Fix**: Add empty-state copy with a "Try it: `curl -X POST ... '{\"content\": \"hello\"}'`" snippet.

**F5.3 — Web Console is not mentioned in `setup`'s "Next steps" output (LOW)**
- `setup.py:77-81` lists 4 follow-up commands but does not say "Open http://localhost:8321/ after `start`". Add it.

---

## Top 5 Quick Wins (<1 hour each, high impact)

| # | Fix | File | Impact |
|---|-----|------|--------|
| 1 | Add 3 screenshots (Console dashboard, graph view, terminal). Embed dashboard at top of both READMEs. | `repo_pages/public/screenshots/`, `README.md:13`, `README_ZH.md:13` | HIGH — kills the "is this real?" doubt |
| 2 | Catch broad `httpx.HTTPError + ValueError` in `status`, `stop`, and the readiness probe in `start`. Use `trust_env=False` for local probes. | `cli/commands/status.py:25`, `start.py:45-53`, `stop.py:30` | HIGH — eliminates raw tracebacks for the 3 most common debug commands |
| 3 | Add `help=` strings to every `setup` option, plus a "What this does" prose block at the top of `setup_cmd.__doc__`. | `cli/commands/setup.py:27-32` | MED — `--help` becomes self-documenting |
| 4 | Make `POST /api/v1/admin/consolidate` return HTTP 503 with actionable JSON when `llm_api_key` is unset; add a 2-line callout in README Quick Start. | `server/routers/admin.py:25`, `README.md:73` | HIGH — kills the "succeeded: 0" confusion |
| 5 | Add `hebb reset` (or document `init --force` as the reset path with a confirmation prompt) and update CHANGELOG.md from v0.1.0 → current state. | `cli/commands/init.py:94`, `CHANGELOG.md` | MED — restores "this project is alive" signal and gives users an escape hatch |

---

## Appendix: Verified Commands

| Command | Result |
|---------|--------|
| `hebb --help` | OK, 14 commands listed cleanly |
| `hebb init --dir /tmp/hippo-test-fresh` | OK, clear output, but writes legacy embedding_model |
| `hebb setup --help` | Bare; no `help=` on options |
| `hebb doctor` | OK, table-rendered, useful |
| `hebb config list` | OK, but `home: null` vs `workspace: ...` row is confusing |
| `hebb config set unknown_key foo` | Decent; lists available keys |
| `hebb config set port abc` | Raw Pydantic error |
| `hebb status --url http://127.0.0.1:9999` | **Raw 50-line traceback** |
| `hebb start` (proxy env active) | **Raw 50-line traceback during readiness probe** |
| `curl POST /api/v1/admin/consolidate` (no LLM key) | Returns `{"processed":0,"succeeded":0,"failed":0}` — silent no-op |
