# Examples & Demos Audit

**Date**: 2026-05-15
**Scope**: Inventory runnable examples, demo assets, and integration coverage in `hebb-mind` v0.1.1; compare against `mem0`, `letta`, `zep`.

---

## TL;DR

There is **no `examples/` directory**, **no notebooks**, **no scripted use-case demos**, and **no media assets** (screenshots, GIFs, video, live demo URL) anywhere in the public-facing repo. The README quick-start stops at `install + start server + curl` — it never shows the framework solving a real problem (e.g. a chatbot that remembers across sessions). `eval/` exists but results are buried in a timestamped folder; only LoCoMo (37.6%) and LongMemEval are reported, with no comparison table or reproduction script. Integrations ship for Claude Code and Codex only — LangChain, LlamaIndex, AutoGen, CrewAI, OpenAI Agents SDK, and plain Python SDK are absent. Mem0 and Letta both ship rich `examples/` (multiagent, multimodal, customer-bot, Discord bot, CharacterAI clone, notebook tutorials) plus hosted live demos. **Hebb Mind is not demo-ready for a public launch** — the framework looks like a server, not a usable memory layer.

---

## Inventory of Current Examples (by location)

| Location | Contents | Type | Verdict |
|---|---|---|---|
| `/examples/` | does not exist | — | **Missing** |
| `/docs/` | empty (placeholder) | — | **Missing** |
| `/scripts/` | only `install.sh` (one-liner installer) | infra | not a demo |
| `/repo_pages/quick-start.md` | `pip install` + `curl` against REST API | doc snippet | minimal — no end-to-end story |
| `/repo_pages/guide/{claude-code,codex,mcp-integration}.md` | install instructions + tool list | config doc | no walkthroughs |
| `/repo_pages/public/` | only `logo.svg` | asset | no screenshots/GIFs |
| `/eval/benchmarks/` | LoCoMo, LongMemEval, ConvoMem, PersonaMem, MemoryArena adapters | benchmark code | runnable but undocumented in README |
| `/eval/reports/2026041*` | one populated run (LoCoMo 37.6%, LongMemEval) | result artifact | not surfaced to users; no comparison vs mem0/letta/zep |
| `/.research/mempalace/examples/` | reference material (not ours) | external | not shippable |
| `/src/hebb/integrations/` | `claude_code/`, `codex/` only | code | working integrations, but no usage demo |
| `/src/hebb/static/index.html` | Web Console SPA (1 page, ~5KB) | asset | exists but no screenshot of it anywhere in docs/README |

**Notebooks (`*.ipynb`) anywhere in repo: 0.**
**Live demo URL: none.** **Demo video/GIF: none.** **Hosted playground: none.**

---

## Gap Analysis vs mem0 / letta / zep

| Capability | mem0 | letta | zep | **Hebb Mind** |
|---|---|---|---|---|
| Top-level `examples/` dir | yes (9+ subdirs: multiagents, multimodal, openai-inbuilt-tools, vercel-ai-sdk-chat-app, yt-assistant-chrome, graph-db-demo) | yes (Discord bot, CharacterPlus, chatbot — separate repos) | yes (notebooks, langgraph quickstart) | **no** |
| Cookbooks / notebooks | yes (`cookbooks/`) | yes (`letta-tutorial` repo) | yes | **no** |
| Plain-Python SDK quickstart | yes (5-line `Memory()`) | yes | yes | **no** (REST `curl` only) |
| LangChain / LangGraph | yes (customer-bot, RAG) | yes | yes | **no** |
| LlamaIndex / CrewAI / AutoGen | yes / yes / yes | yes / community / — | yes / — / — | **no** |
| OpenAI Agents SDK | yes | yes | yes | **no** |
| Discord / Slack / Telegram bot | community | yes (official) | community | **no** |
| Vercel AI SDK / Next.js chat | yes | yes (`letta-chatbot-example`) | yes | **no** |
| Multimodal demo | yes | partial | no | **no** |
| Live hosted demo | yes (mem0.ai) | yes (Letta Cloud) | yes (Zep Cloud) | **no** |
| Screenshot/GIF in README | yes | yes | yes | **no** |
| Benchmark results + comparison table | yes (LoCoMo leaderboard) | yes | yes | partial (internal only) |
| Browser extension / consumer demo | yes | — | — | **no** |

**Coverage gap is the largest deficit vs peers.** Mem0 treats `examples/` as a marketing surface — every integration has a working app.

---

## "Showcase" Examples We MUST Ship Before Going Public

Ranked by impact-per-effort. Each has a single audience and lives in a predictable location so users find it within 30 seconds.

| # | Example | Audience | Location | Deps | Why |
|---|---|---|---|---|---|
| 1 | `python_sdk_basics.py` — 30 lines: store / search / consolidate / dump graph via a `Client`. | every PyPI visitor evaluating in <2 min | `examples/quickstart/` | `hebb-mind` (+`requests`) | The only quickstart today is `curl` — loses Python devs instantly. **Highest priority.** |
| 2 | `persistent_chat.py` + Streamlit variant — multi-turn chatbot with OpenAI/Anthropic + cross-session recall. | AI app builders ("does it actually remember?") | `examples/chatbot/` | `openai`/`anthropic`, `streamlit`/`gradio` | Canonical memory-framework demo. Mem0's homepage is this. |
| 3 | `langchain_memory.py` + `langgraph_customer_bot/` — `HebbMindMemory` adapter and LangGraph node. | LangChain developers (largest agent-framework user base) | `examples/integrations/langchain/` | `langchain`, `langgraph` | Parity with mem0/letta/zep. Without this, invisible to LangChain users. |
| 4 | `openai_agents_sdk.py` — Agent with `write_memory`/`search_memory` as tools. | OpenAI ecosystem users | `examples/integrations/openai_agents/` | `openai-agents` SDK | Hottest agent SDK in 2026; mem0 already has it. |
| 5 | `01_memory_lifecycle.ipynb` — Jupyter walkthrough of ingest → consolidate → retrieve → forget; NetworkX tag graph, TTL decay plots. | researchers, evaluators, writers | `examples/notebooks/` | `jupyter`, `matplotlib`, `networkx` | Differentiator — neuro-inspired story is best told visually. |
| 6 | `llamaindex_memory.py` + `crewai_team.py` — LlamaIndex `Memory` plug-in; CrewAI crew sharing one Hebb Mind. | framework users; multi-agent shared memory | `examples/integrations/{llamaindex,crewai}/` | respective frameworks | Closes the integration matrix to parity. |
| 7 | `reproduce_locomo.sh` + `repo_pages/benchmarks.md` — one-command repro with comparison table vs mem0/letta/zep. | technical evaluators, reviewers, bloggers | `examples/eval/` | `[dev]` extras, LLM key | Turns buried `eval/reports/` into a credibility weapon; starts a leaderboard. |

---

## Demo Asset Gaps

| Asset | Status | Required For |
|---|---|---|
| Web Console screenshot (memory list, search, graph) | missing | README hero, docs landing |
| GIF: "ask → cross-session recall" | missing | README, social posts |
| 90s video walkthrough (Loom/YouTube) | missing | docs landing, talks |
| Live demo URL (read-only seeded console) | missing | mem0/letta both have one |
| Knowledge-graph viz screenshot/GIF | missing | `concepts/knowledge-graph.md` |
| Consolidation before/after diagram | missing | `concepts/consolidation.md` |
| Benchmark comparison chart PNG | missing | README "why Hebb Mind" |
| Claude Code hooks terminal cast | missing | `guide/claude-code.md` |

**Quick win**: one afternoon — (1) 30s GIF of Web Console, (2) 60s asciinema of `pip install → setup → start → first memory → recall`, (3) one PNG of the knowledge graph. Embed all three at the top of README.

---

## Bottom Line

The framework is technically sound and the docs site is well-structured, but a public launch today would land flat: a developer arriving via PyPI sees a server they can `curl`, no Python idiom, no app to run, no picture of the product, and no proof it beats mem0. Shipping items 1-2 plus the three demo assets would close the most embarrassing gap in a single sprint; items 3-7 bring full ecosystem parity over 2-3 sprints.
