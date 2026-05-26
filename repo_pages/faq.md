# FAQ

Short answers to questions that come up before reading the docs in depth. For symptom-driven help see [Troubleshooting](./troubleshooting.md).

---

## Do I need an LLM API key?

No, for ingest, vector search, CRUD, and the Web Console. **Yes**, for consolidation, conflict resolution, importance scoring, and tag extraction. Without a key, `POST /api/v1/admin/consolidate` runs but processes zero memories. Set one with `hebb config set llm_api_key sk-...`.

## Which LLMs are supported?

Anything [LiteLLM](https://github.com/BerriAI/litellm) supports — OpenAI, Anthropic, Google, Azure, Bedrock, Qwen, GLM, Kimi, Ollama, vLLM, and many others. Switch with `hebb config set llm_model <provider>/<model>` and, for non-OpenAI endpoints, `llm_base_url`. See [Multi-model](./advanced/multi-model.md).

## Where is my data stored?

In a SQLite file plus a JSON knowledge graph in your workspace directory. Run `hebb config get workspace` to see the resolved path. Default order: `$HEBB_HOME` → nearest `hebb.json` → `~/.hebb/`.

## Can I use this in production?

v0.1.x is **labeled experimental**. CRUD and search are stable; consolidation and forgetting policies may change in minor releases. The HTTP server has no built-in auth and CORS is wide open by default — put it behind a reverse proxy with auth before exposing it. PostgreSQL is supported for higher concurrency.

## How does it compare to mem0?

Both store agent memories with embeddings. Hebb Mind differs by (a) running as a single local binary with a built-in Web Console and MCP server, (b) implementing a neuroscience-inspired consolidation cycle (encoding → consolidation → forgetting), and (c) defaulting to fully local inference. mem0 has more managed-cloud polish; we have more local control. See [Migration from mem0](./guide/migration.md#from-mem0).

## Is the Web Console multi-tenant?

No. The Console (and the underlying API) currently operates on a single workspace at a time, with no auth and no per-user isolation. Use **partitions** (`partition_id`) to separate logical buckets of memory inside one instance, but treat them as namespaces, not security boundaries.

## How do I export my memories?

The HTTP API can dump them all:

```bash
curl "http://localhost:8321/api/v1/memories?limit=200&offset=0" > memories.json
```

For a full backup, copy the workspace files (see "How do I back up the database?" below). A first-class `hebb export` command is on the roadmap.

## How do I back up the database?

Stop the service first to avoid copying a half-written WAL, then copy the workspace:

```bash
hebb service stop
cp -a "$(hebb config get workspace)" ~/backup/hebb-$(date +%Y%m%d)
hebb service start
```

For PostgreSQL, use `pg_dump` against the URL set in `pg_url`.

## Can I run it on PostgreSQL?

Yes:

```bash
hebb config set storage_type postgresql
hebb config set pg_url "postgresql://user:pass@host:5432/hebb"
```

The schema is created automatically on first start. See [Storage Backends](./advanced/storage-backends.md) for `pgvector` requirements.

## Is there a hosted version?

Not currently. Hebb Mind is designed to run locally or on your own infrastructure. If a hosted option appears in the future it will be announced on the [GitHub repo](https://github.com/afx-team/hebb-mind).

## How do I deploy with Docker?

A reference image and `docker-compose.yml` (with PostgreSQL + pgvector) live in [Storage Backends → Docker](./advanced/storage-backends.md#docker-deployment). The short version:

```bash
docker run -p 8321:8321 -v ~/.hebb:/data ghcr.io/afx-team/hebb-mind:latest
```

## What's the license?

MIT. See [LICENSE](https://github.com/afx-team/hebb-mind/blob/main/LICENSE) in the repo. You can use it commercially, modify it, redistribute it — just keep the copyright notice.

## How do I contribute?

Issues, PRs, and discussion are welcome at <https://github.com/afx-team/hebb-mind>. The most useful contributions right now are: real-world bug reports with `hebb doctor` output, integration recipes (Cursor / Continue / Cline), and benchmark reproductions on hardware we don't own. See `CONTRIBUTING.md` in the repo root.

## Why "Hebb Mind"?

**Hebb Mind** is named after **Donald O. Hebb** (1904–1985), the Canadian neuropsychologist whose 1949 book *The Organization of Behavior* gave us Hebbian learning — *"neurons that fire together, wire together."* That rule is the heart of the framework: the tag knowledge graph wires co-occurring concepts together and strengthens the link each time they recur, while consolidation keeps what is reinforced and forgetting prunes the rest.

The **hippocampus** — the project's original name — lives on inside Hebb Mind as the name of the working-memory partition (`mem_hippocampus`): the inbox where new memories land before consolidation, mirroring the brain region that gates new experience into long-term memory. See [Memory Lifecycle](./concepts/memory-lifecycle.md).

## Is the embedding model multilingual?

It depends on what `hebb setup` selected. `--language en` defaults to an English-only model (`BAAI/bge-large-en-v1.5`, dim 1024). `--language zh` or `--language multi` selects `BAAI/bge-m3` (multilingual, dim 1024). To swap models after install — including the dimension-change → re-embed flow — see [Switch the Embedding Model](./guide/switch-embedding-model.md).
