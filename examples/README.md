# Hebb Mind Examples

Runnable examples that show what the Hebb Mind memory framework actually does.
Each example is self-contained and can be read in under five minutes.

> **Heads up.** The Python facade (`from hebb import HebbMind`) is still
> pre-1.0 — APIs may shift before 1.0; we'll call out breaking changes in the
> [CHANGELOG](../CHANGELOG.md).

---

## Pick your starting point

```
Want to call Hebb Mind from Python?           ──→  01_python_sdk_basics.py
Want a chatbot that remembers across runs?      ──→  02_persistent_chat.py
Want your AI coding agent to use Hebb Mind?   ──→  03_mcp_quickstart.md
Want to see (or reproduce) benchmark numbers?   ──→  04_benchmarks_locomo.md
Want to plug Hebb Mind into LangChain?        ──→  05_langchain_adapter.py  (WIP)
Want to wire Hebb Mind into LlamaIndex / CrewAI / AutoGen / LangGraph?
                                              ──→  Python Framework Integration guide
```

## Table of contents

| # | File | What it shows |
|---|------|---------------|
| 01 | [`01_python_sdk_basics.py`](./01_python_sdk_basics.py) | The five-minute SDK tour: `add` / `search` / `list` / `delete` / `consolidate`. |
| 02 | [`02_persistent_chat.py`](./02_persistent_chat.py) | A CLI chat loop that remembers facts across restarts. Uses LiteLLM. |
| 03 | [`03_mcp_quickstart.md`](./03_mcp_quickstart.md) | One command to wire Hebb Mind into Claude Code or Codex via MCP. |
| 04 | [`04_benchmarks_locomo.md`](./04_benchmarks_locomo.md) | Reproduce the LoCoMo number reported in the README. |
| 05 | [`05_langchain_adapter.py`](./05_langchain_adapter.py) | **WIP** skeleton for a LangChain adapter — contributions welcome. |

---

## Prerequisites

```bash
# 1. Install the package (editable from a checkout, or from PyPI)
pip install -e .          # from a clone of this repo (inside a venv)
# OR
pipx install hebb-mind    # from PyPI (isolated CLI install)

# 2. Optional: pre-download the local embedding model (small model, only if
#    not already cached — ~90MB English / ~470MB multilingual)
hebb setup

# 3. Copy the env template and fill in at least one LLM key for example 02
cp examples/.env.example examples/.env
$EDITOR examples/.env
```

### Environment variables used by the examples

| Variable | Used by | Required? |
|----------|---------|-----------|
| `OPENAI_API_KEY` (or any LiteLLM provider key) | `02_persistent_chat.py` | No — falls back to a local stub responder if absent. |
| `HEBB_HOME` | All Python examples | No — the workspace directory; defaults to `./examples/data` (the DB lands at `<HEBB_HOME>/hebb.db`). |

LiteLLM supports many providers (Anthropic, DeepSeek, Azure, Bedrock, Ollama,
…). Set the matching env var and pass `--model` to example 02. See the
[LiteLLM provider list](https://docs.litellm.ai/docs/providers).

---

## Running an example

```bash
# Example 01 — SDK basics. The --reset flag wipes the example workspace DB so
# you can re-run cleanly.
python examples/01_python_sdk_basics.py --reset

# Example 02 — chat. Quit with Ctrl-D or "/quit", then re-run to see recall.
python examples/02_persistent_chat.py

# Example 04 — benchmarks. Read the doc; the actual command lives in eval/.
```

---

## Contributing more examples

The audit (`reports/analysis/audit-examples.md`) lists the next examples we'd
love to see: LangChain (#5 here is a starting skeleton), LlamaIndex, OpenAI
Agents SDK, CrewAI, and a Jupyter walkthrough of the consolidation lifecycle.
Copy-paste recipes for LlamaIndex / CrewAI / AutoGen / LangGraph live in the
[Python Framework Integration guide](https://afx-team.github.io/hebb-mind/guide/framework-integrations.html);
PRs welcome — please keep each example self-contained and under ~200 lines.
