# Contributing to Hippocampus

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=hippocampus

# Single file
pytest tests/test_storage.py -v
```

## Code Quality

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Lint
ruff check src/

# Auto-fix
ruff check src/ --fix

# Type check
mypy src/hippocampus/
```

## Project Structure

```
src/hippocampus/
    config/       Settings + config loading
    models/       Pydantic data models
    storage/      Storage backends (SQLite, PostgreSQL)
    embedding/    Text embedding providers
    retrieval/    Memory search + scoring
    graph/        Tag knowledge graph
    agents/       LLM-powered memory agents
    scheduler/    Background jobs
    server/       FastAPI REST API
    cli/          CLI commands
```

## Adding a New Storage Backend

1. Implement the `MemoryStore` and `PartitionStore` protocols from `storage/base.py`
2. Add a migration file for your database schema
3. Register the backend in `storage/factory.py`
4. Add optional dependencies to `pyproject.toml`

## Pull Request Guidelines

1. **Fork and branch** — Create a feature branch from `main`
2. **Test** — Add tests for new functionality. Run `pytest` before submitting
3. **Lint** — Ensure `ruff check src/` passes with no errors
4. **Commit messages** — Use clear, descriptive commit messages
5. **PR description** — Explain what your change does and why

## Reporting Issues

- Use [GitHub Issues](https://github.com/afx-team/hippocampus/issues)
- Include steps to reproduce, expected behavior, and actual behavior
- Include your Python version, OS, and hippocampus version

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
