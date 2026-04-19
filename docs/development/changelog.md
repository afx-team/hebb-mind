# Changelog

## [0.1.0] - 2026-04-17

Initial release.

### Added

- **Memory partitions** -- 5 brain-inspired partitions (hippocampus, semantic, episodic, preference, procedural) + custom partitions
- **Memory consolidation** -- LLM-powered agent that processes working memory into long-term partitions via Agentic RAG
- **Dynamic forgetting** -- Exponential decay TTL formula based on access frequency and importance
- **Knowledge graph** -- Tag-based graph with co-occurrence edges, backed by NetworkX + JSON
- **Storage backends** -- SQLite + sqlite-vec (default), PostgreSQL + pgvector (optional)
- **REST API** -- Full CRUD for memories and partitions, search, graph queries, admin endpoints
- **GitHub OAuth** -- Optional multi-user authentication (single-user local mode by default)
- **CLI** -- `hippocampus init`, `hippocampus start`, `hippocampus status`
- **Docker** -- Dockerfile + docker-compose for one-command deployment
- **Installer** -- `curl | sh` with interactive mode for backend selection
- **Multi-model support** -- OpenAI, Anthropic, Qwen, GLM, Kimi via LiteLLM
- **Web Console** -- Built-in web interface for memory management, search, and graph visualization
- **Evaluation benchmarks** -- LoCoMo, LongMemEval, ConvoMem, PersonaMem
