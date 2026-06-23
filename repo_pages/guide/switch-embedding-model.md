---
description: "Switch the embedding model behind your AI agent memory: local sentence-transformers or LiteLLM API, handle dimension changes, and re-embed with resume."
---

# Switch the Embedding Model

`hebb setup` picks a **small** embedding model from your OS locale on first run, and downloads it only if it isn't already cached. By default (`--profile default`) that is `all-MiniLM-L6-v2` (384-d, English) or `intfloat/multilingual-e5-small` (384-d, multilingual); the high-quality bge tier — `BAAI/bge-large-en-v1.5` / `BAAI/bge-m3` (both 1024-d) — is opt-in via `hebb setup --profile best`. You can switch to any other [sentence-transformers](https://www.sbert.net/docs/pretrained_models.html)-compatible model — or any LiteLLM-compatible cloud embedding API — at any time, even after the service has been running and storing memories. A model that is already cached is reused; only missing models are downloaded.

A common upgrade is moving from the small default to the bge tier for stronger retrieval — that is a **dimension change** (384 → 1024), so follow the "Different dimension" row below.

Switching falls into one of three cases. Pick the section that matches yours.

| Case | What changes | What you need to do |
|------|--------------|---------------------|
| **Same dimension, different model** (e.g. `all-MiniLM-L6-v2` → `intfloat/multilingual-e5-small`, both 384-d) | Stored vectors keep working until you re-embed | Update config → restart → optionally re-embed for consistency |
| **Different dimension** (e.g. `all-MiniLM-L6-v2` 384 → `BAAI/bge-large-en-v1.5` 1024) | Vector table is auto-reset on next start; old vectors are lost | Update config → restart → **run `hebb memory reembed`** |
| **Local → API or vice versa** | Provider, base URL, API key all change | Use the Web Console or set each field via CLI, then restart |

## Path A — CLI, one-shot (recommended)

`hebb model prefetch --model <id>` updates `embedding_model`, `embedding_provider`, and `embedding_dim` in `hebb.json` in a single command, then downloads and verifies the model.

```bash
# Switch to the multilingual bge-m3 (1024-d)
hebb model prefetch --model BAAI/bge-m3 --region auto

# Apply by restarting the service
hebb service restart

# If the dimension changed, repopulate vectors for existing memories
hebb memory reembed
```

`--region auto` probes HuggingFace's official endpoint and the `hf-mirror.com` mirror, picking the faster one. Force a specific source with `--region cn` (mirror) or `--region global` (official).

## Path B — CLI, manual fields

If you already have the model cached locally and just want to flip the config:

```bash
hebb config set embedding_provider local
hebb config set embedding_model intfloat/multilingual-e5-large
hebb config set embedding_dim 1024          # only set when you know the dim
hebb service restart
hebb memory reembed                          # if dim changed
```

For an API provider:

```bash
hebb config set embedding_provider api
hebb config set embedding_model openai/text-embedding-3-small
hebb config set embedding_base_url https://api.openai.com/v1
hebb config set embedding_api_key sk-...
hebb config set embedding_dim 1536
hebb service restart
hebb memory reembed
```

## Path C — Web Console

Open <http://localhost:8321/#system/embedding> (the **System → Embedding** tab), then:

1. **Pick a preset** from the dropdown (or choose *Custom* and type a model ID).
2. **Test Embedding** — local models download in the background with a live progress bar; cached models and API providers verify in one round-trip.
3. **Save** — fields that require a restart trigger a "Restart now?" prompt. Confirming restarts the service, polls `/health`, and reloads the page.
4. If the dimension changed, run `hebb memory reembed` in a terminal afterwards. (Re-embed from the Web Console is on the roadmap.)

## Re-embed: what it actually does

`hebb memory reembed` walks every memory in storage, re-encodes the content with the **currently configured** embedder, and writes the new vector back.

```bash
hebb memory reembed                      # all partitions
hebb memory reembed --partition mem_user # one partition
hebb memory reembed --dry-run            # count without writing
hebb memory reembed --batch-size 128 -y  # bigger batches, no prompt
hebb memory reembed --restart            # discard any existing checkpoint
```

### Resume after interruption

The command writes a tiny checkpoint file at `<workspace>/reembed.checkpoint.json` and flushes every ~32 memories. If you interrupt with **Ctrl-C**, close the lid, lose power, or the process is killed any other way, **just run the same command again** — it picks up the remaining memories and skips the ones already done.

The checkpoint identity is the triple `(target_model, target_dim, partition_id)`. If the next run sees a different value for *any* of those (you changed `embedding_model`, changed the dim, or now passed `--partition`), the stale checkpoint is automatically discarded and a fresh full pass starts. Use `--restart` to force-discard a checkpoint even when the identity matches.

The checkpoint is removed automatically on successful completion. A typical sequence looks like:

```
$ hebb memory reembed
Re-embed every memory in all partitions using model 'BAAI/bge-m3' (dim=1024)? [y/N]: y
Scanning memories…
  Re-embedding ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% • 0:02:14
Re-embedded this run: 1283
Re-embed complete: 1283 memories updated. Checkpoint removed.
```

After Ctrl-C at 47 %:

```
$ hebb memory reembed
^C
Interrupted. Checkpoint saved with 678 memories remaining.

$ hebb memory reembed
Resuming previous reembed for model BAAI/bge-m3 (dim=1024): 605/1283 (47.2%) already done, 678 remaining.
  Re-embedding ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% • 0:01:11
Re-embed complete: 678 memories updated. Checkpoint removed.
```

## Troubleshooting

**Download stalls in the Web Console.** Open the Embedding section, switch `hf_endpoint` to `https://hf-mirror.com`, Save (no restart needed for this field), Test again. Or run `hebb model prefetch --region cn` from a terminal — same effect.

**`update_embedding` fails with a dimension mismatch error.** The vector table still has the old dimension; this happens if the service wasn't restarted after the config change. Run `hebb service restart` first, then `hebb memory reembed`.

**`hebb` not found after install.** See [Installation → Install pipx](./installation.md#install-pipx-if-you-don-t-have-it).

## See also

- [Configuration reference](./configuration.md) — full list of `embedding_*` fields
- [Multi-model support](../advanced/multi-model.md) — local vs API trade-offs, language selection
- [Storage backends](../advanced/storage-backends.md) — vector table internals (SQLite vec0 / pgvector)
