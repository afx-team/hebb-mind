# Hebb Mind

Agent memory framework — open-source project under [github.com/afx-team](https://github.com/afx-team).

---

## Priority Hierarchy

When rules conflict, follow this priority order:
1. **MUST** — Non-negotiable constraints (违反则输出无效)
2. **SHOULD** — Strong recommendations (默认遵守，可明确说明理由后偏离)
3. **MAY** — Optional suggestions (视具体情况采用)

---

## Project Context

**Type**: Research & design phase → Production implementation
**Domain**: Agent memory for LLMs (inspired by hippocampus = memory consolidation center)
**Organization**: [github.com/afx-team](https://github.com/afx-team)

### Current Phase Focus
- [ ] Survey academic papers on agent memory
- [ ] Analyze open-source memory implementations  
- [ ] Design Hebb Mind architecture
- [ ] Implement core components

---

## Directory Architecture

```
hebb-mind/
├── repo_pages/           # VuePress site → GitHub Pages (PUBLIC-FACING)
│   ├── .vuepress/        # VuePress configuration
│   └── *.md              # Public documentation pages
├── reports/              # Internal research outputs (NOT for publication)
│   ├── papers/           # Academic paper notes and summaries
│   ├── analysis/         # Open-source project analysis reports
│   ├── design/           # Architecture and design documents
│   └── surveys/          # Research survey reports
├── src/                  # Source code (TBD)
├── eval/                 # Benchmark evaluations on open datasets
└── results/              # Evaluation outputs
```

**CRITICAL DISTINCTION**:
- `repo_pages/` = **Public website** (VuePress → GitHub Pages) — curated documentation for users
- `reports/` = **Internal research** — raw notes, analysis, design drafts (not for publication)

**File Placement Rules**:
| Content Type | Location | Visibility |
|-------------|----------|------------|
| User documentation | `repo_pages/` | Public (GitHub Pages) |
| Paper summaries | `reports/papers/` | Internal |
| Project analysis | `reports/analysis/` | Internal |
| Architecture design | `reports/design/` | Internal |
| Research surveys | `reports/surveys/` | Internal |

**MUST NOT**:
- Put research notes in `repo_pages/` — they go in `reports/`
- Put public docs in `reports/` — they go in `repo_pages/`
- Commit sensitive analysis to `repo_pages/` (it will be published)

---

## Output Standards (MUST)

### Document Formats

| Document Type | Required Sections | File Naming |
|--------------|-------------------|-------------|
| Paper Note | Summary, Key Insights, Implications for Hebb Mind | `[AuthorYear]-[topic].md` |
| Analysis Report | Overview, Architecture, Strengths, Weaknesses, Implications | `[project-name]-analysis.md` |
| Design Doc | Problem, Solution, Trade-offs, Implementation Plan | `[feature-name]-design.md` |

### Code Standards (when implementing)

```python
# MUST: Type hints on all public functions
def process_memory(memory: Memory) -> ProcessedMemory:
    ...

# MUST: Docstring with Args, Returns, Raises for public APIs
def retrieve(query: str, k: int = 5) -> list[Memory]:
    """Retrieve top-k relevant memories.
    
    Args:
        query: Search query string
        k: Number of results to return
        
    Returns:
        List of Memory objects sorted by relevance
    """
    ...

# MUST: Unit tests for core workflows
def test_retrieve_returns_sorted_memories():
    ...
```

---

## Constraints (MUST NOT)

- **DO NOT** use relative imports outside the same module
- **DO NOT** hardcode API keys or secrets
- **DO NOT** create files outside defined directory structure
- **DO NOT** skip the "Implications for Hebb Mind" section in analysis papers
- **DO NOT** use Chinese and English interchangeably in the same document — be consistent

---

## Conventions (SHOULD)

### Visual Documentation
- Use **mermaid diagrams** for architecture, data flow, and component relationships
- Example:
  ```mermaid
  graph LR
    A[Input] --> B[Process] --> C[Output]
  ```

### Academic References
- Format: `[Author et al., Year]` or `[Author, Year]` for single author
- Example: "Memory consolidation (Wilson & McNaughton, 1994) shows that..."

### Actionability Check
- Every analysis document **SHOULD** end with actionable insights
- Standard section: "## Implications for Hebb Mind"

---

## Engineering Principles

1. **Architecture Clarity** — Directory structure = module boundaries
2. **Semantic Naming** — Names reveal intent, not implementation
3. **Multi-Model Support** — Design for Codex, GPT, Llama compatibility
4. **Test Coverage** — Unit tests for logic, E2E tests for workflows
5. **Incremental Complexity** — Start simple, add abstraction when pattern repeats 3+ times

---

## Decision Guidelines

### When to Create New Module
- **YES** if: Component has independent lifecycle, clear API boundary, or >500 lines
- **NO** if: Just organizing related functions — use a class or namespace instead

### When to Add Abstraction Layer
- **YES** if: Pattern appears 3+ times across codebase
- **NO** if: Only used once or twice — wait for pattern to stabilize

### When to Write Design Doc
- **YES** if: Affects 2+ modules, introduces new dependency, or changes API contract
- **NO** if: Local refactor, bug fix, or single-module improvement

---

## Quality Checklist

Before marking any task complete, verify:

- [ ] File placed in correct directory
- [ ] Naming follows specified convention
- [ ] Document has all required sections
- [ ] Code has type hints and tests (if applicable)
- [ ] Commit message explains "why" not "what"

---

## Quick Reference

| Task | Location | Template |
|------|----------|----------|
| Public documentation | `repo_pages/` | VuePress page format |
| Paper summary | `reports/papers/` | See `reports/papers/.template.md` |
| Project analysis | `reports/analysis/` | See `reports/analysis/.template.md` |
| Architecture design | `reports/design/` | See `reports/design/.template.md` |