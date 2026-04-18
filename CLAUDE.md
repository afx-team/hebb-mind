# Hippocampus


Agent memory framework — open-source project under [github.com/afx-team](https://github.com/afx-team).

## Project Context

This project builds an open-source agent memory system inspired by neuroscience (hippocampus = memory consolidation center). Currently in **research & design phase**.

## Team 

- **Organization**: github.com/afx-team
- **Research focus**: Agent memory for LLMs — surveying academic papers, analyzing open-source projects, designing our own architecture

## Directory Structure

```
docs/
  papers/       # Academic paper notes and summaries
  analysis/     # Open-source project analysis reports
  design/       # Architecture and design documents
  surveys/      # Research survey reports
src/            # Source code (TBD)
eval/           # 系统在开源测试数据集上的评测
results
```

## Available Skills

- `/arxiv-search <query>` — Search arxiv papers
- `/github-explore <owner/repo>` — Deep-dive into a GitHub repo
- `/research-survey <topic>` — Comprehensive research survey
- `/bench-compare <projects>` — Compare memory systems

## Available Agents

- `paper-researcher` — Academic paper research
- `code-analyst` — Open-source code analysis
- `architect` — System architecture design

## MCP Tools

- **context7** — Library documentation lookup
- **github** — GitHub API access (needs GITHUB_TOKEN env var)
- **filesystem** — Enhanced file operations
- **memory** — Persistent memory bank
- **fetch** — HTTP fetch for web resources
- **sequential-thinking** — Structured reasoning

## Conventions

- All research output goes in `docs/` with structured markdown
- Use mermaid diagrams for architecture visuals
- Reference papers by `[Author et al., Year]` format
- Keep analysis reports actionable — always end with "implications for hippocampus"

## Engineering Principles  

1. Clear architecture — directory structure reflects architecture, modular design
2. Global configuration, semantic naming
3. Support for mainstream models
4. Production-grade code quality
5. Unit tests + end-to-end tests for core workflows
