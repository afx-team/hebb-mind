# Installation

## From PyPI (Recommended)

```bash
pip install afx-hippocampus
```

Requires **Python >= 3.10**.

## Optional Extras

Hippocampus ships with optional dependency groups for different use cases:

| Extra | Command | Description |
|-------|---------|-------------|
| PostgreSQL | `pip install afx-hippocampus[pg]` | PostgreSQL + pgvector storage backend |
| Development | `pip install afx-hippocampus[dev]` | Testing, linting, type-checking, and benchmark evaluation tools |

Install multiple extras at once:

```bash
pip install afx-hippocampus[pg,dev]
```

## One-line Installer

For a guided installation with interactive backend selection:

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh
```

## From Source

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Verify Installation

```bash
hippocampus --version
```

You should see the installed version number printed to the console.

## What Gets Installed

The `afx-hippocampus` package includes:

- **hippocampus** CLI command
- FastAPI REST server
- SQLite + sqlite-vec storage backend (zero-config)
- Sentence-transformers embedding model (`all-MiniLM-L6-v2`, downloaded on first use)
- NetworkX-based knowledge graph
- APScheduler for background consolidation and forgetting jobs
- LiteLLM for multi-model LLM support

## Next Steps

After installation, initialize your project:

```bash
hippocampus init
hippocampus config set llm_api_key sk-your-key-here
hippocampus start
```

See the [Quick Start](../quick-start.md) guide for a complete walkthrough.
