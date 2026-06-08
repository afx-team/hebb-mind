# Troubleshooting

Symptom → cause → fix for the issues that bite first-time users most often. If something here doesn't match what you're seeing, `hebb doctor` is the next-best one-shot diagnostic, and the [FAQ](./faq.md) covers conceptual questions.

---

## `consolidate` returns `processed: 0` (or no conflicts get resolved)

**Symptom.** You called the endpoint and got back zeros:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
# {"processed":0,"succeeded":0,"failed":0}
```

Or you can see new memories piling up in the database but nothing is being merged, deduplicated, or tagged.

**Cause.** No LLM model is configured. Consolidation, conflict resolution, importance scoring, and automatic tag extraction all call out to an LLM via [LiteLLM](https://github.com/BerriAI/litellm). The on/off gate is **`llm_model`** — until it is set, the consolidation worker silently skips every batch. Vector search and CRUD still work, but nothing "agentic" runs. (A hosted provider also needs `llm_api_key`; a local/proxy model does not.)

**Fix.**

```bash
hebb config set llm_model openai/gpt-4o-mini
# Hosted providers also need a key (skip for local/proxy models):
hebb config set llm_api_key sk-your-key-here
hebb config set llm_base_url https://api.openai.com/v1
# Re-trigger
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

You can verify the model is loaded with `hebb doctor` — it shows `LLM: [OK]` once `llm_model` is set. See [Configuration](./guide/configuration.md) for the full list of supported providers.

---

## `Port 8321 already in use`

**Symptom.** `hebb service install` (or `hebb service restart`) logs `[Errno 48] Address already in use` (macOS/Linux) or `error while attempting to bind on address` (Windows) and the service immediately exits.

**Cause.** Another process is bound to port 8321. Most often it's a previous Hebb Mind instance the service manager kept alive, but it can also be an unrelated service.

**Fix.** Find the process:

```bash
# macOS / Linux
lsof -i :8321
# or
ss -tulpn | grep 8321

# Windows (PowerShell)
Get-NetTCPConnection -LocalPort 8321
```

Then either stop the old server cleanly, or pick another port:

```bash
hebb service stop                  # stop the OS-managed service if it was ours
hebb config set port 8322          # change the port persistently
hebb service restart               # pick up the new port
```

Remember to point any MCP / Claude Code integration at the new port, and update the `--url` arg on `hebb status`.

---

## `database is locked`

**Symptom.** Requests fail intermittently with `sqlite3.OperationalError: database is locked`, usually under concurrent writes (e.g. multiple Claude Code sessions hooking the same workspace).

**Cause.** SQLite serializes writers. Hebb Mind enables WAL mode by default, but heavy concurrent ingest or a stray transaction can still block.

**Fix.**

1. Make sure only one `hebb` server process is touching the file:

   ```bash
   ps aux | grep hebb
   hebb service stop
   ```

2. Confirm WAL mode is on (it should be by default):

   ```bash
   sqlite3 ~/.hebb/hebb.db "PRAGMA journal_mode;"
   # expected: wal
   ```

3. If you're driving high write QPS from multiple processes, switch to PostgreSQL:

   ```bash
   hebb config set storage_type postgresql
   hebb config set pg_url "postgresql://user:pass@host:5432/hebb"
   ```

   See [Storage Backends](./advanced/storage-backends.md) for migration notes.

---

## First start hangs (no output for minutes)

**Symptom.** `hebb setup` or `hebb service install` appears stuck. No progress, no error.

**Cause.** The embedding model is downloading from HuggingFace. The default models are small — `all-MiniLM-L6-v2` (~90MB, English) or `intfloat/multilingual-e5-small` (~470MB, multilingual) — and land in about a minute on a typical connection. If you ran `hebb setup --profile best`, a high-quality model like `BAAI/bge-large-en-v1.5` (~1.3 GB) or `BAAI/bge-m3` (~2 GB) is downloading instead; on a slow link or behind a corporate proxy that can take several minutes to 15+. The progress bar is provided by `huggingface_hub` and is sometimes swallowed when stdout is not a TTY.

**Fix.**

1. Check the model cache to confirm it's actually arriving:

   ```bash
   ls -lah ~/.cache/huggingface/hub/
   ```

   You should see a `models--*` directory (e.g. `models--sentence-transformers--all-MiniLM-L6-v2`, or `models--BAAI--*` for the `best` profile) whose size is growing.

2. If you're in mainland China or behind the Great Firewall, switch the source to the [hf-mirror.com](https://hf-mirror.com) mirror:

   ```bash
   hebb setup --region cn
   ```

   This sets `HF_ENDPOINT=https://hf-mirror.com` before downloading.

3. If a previous download crashed midway, clear the partial cache for the affected model and retry (replace the directory name with the model you're downloading):

   ```bash
   rm -rf ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2
   hebb model prefetch
   ```

The model lives under `~/.cache/huggingface/hub/` (or `$HF_HOME` if you set it). It is *not* re-downloaded on subsequent starts.

---

## Web Console shows nothing

**Symptom.** You open <http://localhost:8321/> and the Memories tab is empty, or the Dashboard reads `0 memories`.

**Cause (most common).** The active workspace is empty — you started the server from a different directory than the one that holds your `hebb.db`. Hebb Mind resolves the workspace as:

1. `$HEBB_HOME` if set
2. The nearest ancestor directory containing `hebb.json`
3. `~/.hebb/` as the global default

**Fix.** Print the resolved location:

```bash
hebb config get workspace
# /Users/you/projects/myapp     (the workspace directory; hebb.db lives inside it)
```

If it's not what you expect, either `cd` into the project that owns the db, or pin it explicitly:

```bash
export HEBB_HOME=/path/to/your/workspace
hebb service restart
```

For a tour of what each Console tab does, see [Web Console](./guide/web-console.md).

---

## MCP server won't start in Claude Code

**Symptom.** Claude Code shows the `hebb` MCP server as `failed` or never lists its tools. `/mcp` inside Claude Code returns nothing for hebb.

**Cause.** Either the integration wasn't registered for the scope you're using, or the Hebb Mind HTTP server isn't running (the MCP entry point is a stdio proxy that talks to <http://localhost:8321>).

**Fix.**

```bash
# 1. Make sure the HTTP server is up
hebb status
# Expected: "Server is running at http://127.0.0.1:8321 (v…)"

# 2. Inspect what Claude Code knows about
claude mcp list

# 3. Re-install at the right scope (project / user / local)
hebb claude-code install --scope user
```

The `--scope user` form writes to `~/.claude/settings.json` and applies to every project. Use `--scope project` to scope the integration to the current directory. After install, fully quit and re-open Claude Code so it re-reads the settings file.

If `hebb claude-code install` itself fails, run `hebb doctor` — it checks for the `claude` CLI on `$PATH` and reports a clear error when it's missing.

---

## Still stuck?

- `hebb doctor` — one-shot health check for the LLM key, embedding model, server, and integration tools.
- [FAQ](./faq.md) — short answers to common conceptual questions.
- [GitHub Issues](https://github.com/afx-team/hebb-mind/issues) — search before filing; include the output of `hebb doctor` and the failing command.
