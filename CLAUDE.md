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

## Conventions

- Use mermaid diagrams for architecture visuals
- Reference papers by `[Author et al., Year]` format
- Keep analysis reports actionable — always end with "implications for hippocampus"

## Engineering Principles  

1. Clear architecture — directory structure reflects architecture, modular design
2. Global configuration, semantic naming
3. Support for mainstream models
4. Production-grade code quality
5. Unit tests + end-to-end tests for core workflows
