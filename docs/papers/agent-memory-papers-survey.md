# Academic Papers Survey: Agent Memory Systems

> Generated: 2026-04-15 | Project: hippocampus

---

## Foundational Papers

### 1. Generative Agents: Interactive Simulacra of Human Behavior
- **Authors**: Park, J.S., O'Brien, J.C., Cai, C.J., Morris, M.R., Liang, P., Bernstein, M.S.
- **Date**: August 2023 (UIST 2023)
- **URL**: https://arxiv.org/abs/2304.03442
- **Key Contributions**:
  - Introduced the **memory stream** architecture — a comprehensive record of an agent's experiences
  - Proposed **retrieval** based on three factors: recency, importance, relevance
  - Introduced **reflection** — agents synthesize higher-level observations from memories
  - Demonstrated emergent social behaviors in a simulated town of 25 agents
- **Memory Architecture**:
  - Memory stream: timestamped natural language observations
  - Retrieval function: `score = α·recency + β·importance + γ·relevance`
  - Reflection: periodic synthesis of memories into higher-level insights
  - Planning: daily/hourly plans derived from reflections and personality
- **Retrieval Strategy**: Weighted combination of recency (exponential decay), importance (LLM-rated 1-10), and relevance (embedding cosine similarity)
- **Practical Impact**: Most cited paper in agent memory; directly influenced Mem0, Letta, and virtually all agent memory projects. The recency-importance-relevance retrieval formula is the de facto standard.

### 2. MemGPT: Towards LLMs as Operating Systems
- **Authors**: Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S.G., Stoica, I., Gonzalez, J.E.
- **Date**: October 2023
- **URL**: https://arxiv.org/abs/2310.08560
- **Key Contributions**:
  - Proposed treating LLM context window like an OS manages virtual memory
  - Introduced a **memory hierarchy**: main context (RAM) ↔ external storage (disk)
  - Agent actively manages its own context through function calls
  - Demonstrated effectiveness in long document QA and multi-session conversations
- **Memory Architecture**:
  - Main context: system prompt + core memory (persona/human blocks) + FIFO message queue
  - Archival storage: vector-indexed long-term storage
  - Recall storage: searchable conversation history
  - Agent uses explicit functions: `core_memory_append`, `archival_memory_insert`, `archival_memory_search`
- **Retrieval Strategy**: Agent-driven — the model decides when and what to retrieve via function calls
- **Practical Impact**: Foundation of Letta platform; introduced the paradigm of agent-managed memory. Influenced the shift from passive to active memory management.

### 3. Cognitive Architectures for Language Agents (CoALA)
- **Authors**: Sumers, T.R., Yao, S., Narasimhan, K., Griffiths, T.L.
- **Date**: September 2023
- **URL**: https://arxiv.org/abs/2309.02427
- **Key Contributions**:
  - Proposed a systematic framework for categorizing language agent architectures
  - Defined memory taxonomy: **working memory** (in-context), **episodic** (experiences), **semantic** (knowledge), **procedural** (code/skills)
  - Mapped cognitive science concepts to LLM agent components
  - Surveyed existing agents (Voyager, Reflexion, DEPS, etc.) through this lens
- **Memory Architecture**:
  - Working memory: current context window contents
  - Episodic memory: past experiences and interactions (retrievable)
  - Semantic memory: world knowledge, facts, beliefs
  - Procedural memory: learned skills, code, action patterns
- **Practical Impact**: Provides the theoretical vocabulary for agent memory research. The episodic/semantic/procedural taxonomy is now widely adopted.

---

## Memory Mechanisms & Strategies

### 4. Reflexion: Language Agents with Verbal Reinforcement Learning
- **Authors**: Shinn, N., Cassano, F., Gopinath, A., Narasimhan, K., Yao, S.
- **Date**: March 2023 (NeurIPS 2023)
- **URL**: https://arxiv.org/abs/2303.11366
- **Key Contributions**:
  - Agents reflect on task failures and store verbal feedback as memory
  - Self-reflection enables learning from mistakes without weight updates
  - Achieved significant improvements on coding, decision-making, and reasoning tasks
- **Memory Architecture**: Sliding window of self-reflective feedback strings
- **Retrieval Strategy**: Recent reflections appended to prompt context
- **Relevance**: Demonstrates that verbal/episodic memory can substitute for fine-tuning

### 5. Voyager: An Open-Ended Embodied Agent with Large Language Models
- **Authors**: Wang, G., Xie, Y., Jiang, Y., Mandlekar, A., Xiao, C., Zhu, Y., Fan, L., Anandkumar, A.
- **Date**: May 2023
- **URL**: https://arxiv.org/abs/2305.16291
- **Key Contributions**:
  - Introduced **skill library** as procedural memory for game agents
  - Agent writes, verifies, and stores reusable code skills
  - Skill retrieval based on task similarity for transfer learning
- **Memory Architecture**: Code-based skill library indexed by task descriptions
- **Retrieval Strategy**: Embedding similarity between current task description and skill descriptions
- **Relevance**: Best example of procedural memory — learned skills as reusable code

### 6. RAISE: Retrieval-Augmented Impersonation of Conversational Social Entities
- **Authors**: Multiple authors
- **Date**: 2023
- **Key Contributions**:
  - Memory architecture for social agents that impersonate personas
  - Dual memory: short-term (recent dialogue) + long-term (historical interactions)
  - Memory-based personality consistency

### 7. SCM: A Shortcut Memory Architecture for Self-Evolving Agents
- **Authors**: Various
- **Date**: 2024
- **Key Contributions**:
  - Proposes experience shortcuts — compressed action patterns from successful task completions
  - Agents learn to skip intermediate reasoning steps for familiar situations
  - Demonstrates efficiency gains through memory-augmented planning
- **Relevance**: Bridges episodic and procedural memory — learned shortcuts are proceduralized episodes

---

## Surveys & Frameworks

### 8. A Survey on the Memory Mechanism of Large Language Model Based Agents
- **Authors**: Zhang, Z., et al.
- **Date**: 2024
- **URL**: https://arxiv.org/abs/2404.13501
- **Key Contributions**:
  - Comprehensive taxonomy of memory mechanisms in LLM agents
  - Categorizes memory by: type (short/long-term), operation (read/write/manage), evolution
  - Reviews memory in single-agent, multi-agent, and human-agent systems
  - Identifies open challenges: memory hallucination, scalability, privacy
- **Practical Impact**: Best reference for understanding the landscape of agent memory research

### 9. PersonaRAG: Enhancing Retrieval-Augmented Generation Systems with User-Centric Agents
- **Date**: 2024
- **Key Contributions**:
  - RAG enhanced with user memory profiles
  - Memory of user preferences improves retrieval relevance
  - Demonstrates value of persistent user modeling

### 10. Zep: A Temporal Knowledge Graph Architecture for Agent Memory
- **Authors**: Zep team (Preston Rasmussen et al.)
- **Date**: 2024-2025
- **URL**: Referenced at https://github.com/getzep/graphiti
- **Key Contributions**:
  - Temporal knowledge graphs for agent memory
  - Bi-temporal model: event time + ingestion time
  - Entity resolution across conversations
  - Graph-based retrieval outperforms vector-only approaches on memory tasks
- **Practical Impact**: Bridges academic graph memory research with production systems

---

## Emerging Research Directions (2024-2026)

### 11. Memory Consolidation & Forgetting
- **Key Papers**: Multiple works on applying Ebbinghaus forgetting curves to agent memory
- **Trends**:
  - Spaced repetition for memory reinforcement
  - Importance-based forgetting (low-importance memories decay faster)
  - Sleep-like consolidation phases where memories are reorganized
  - Active forgetting for privacy and relevance

### 12. Multi-Agent Shared Memory
- **Trends**:
  - Shared blackboard architectures for agent teams
  - Memory-as-a-service patterns
  - Federated memory with access control
  - Collective intelligence through shared episodic memory

### 13. Hierarchical & Compositional Memory
- **Trends**:
  - Multi-level abstraction (raw → summarized → conceptual)
  - Memory indices that support different query patterns
  - Compositional retrieval combining multiple memory types

### 14. Memory3: Language Modeling with Explicit Memory
- **Key Idea**: Explicit memory as model parameters alternative
- **Approach**: Memory tokens stored externally, loaded on demand
- **Relevance**: Hardware-level memory augmentation, different paradigm from application-level

---

## Emerging Trends Summary

1. **From passive to active memory**: Agents increasingly manage their own memory (MemGPT paradigm winning)
2. **Graph over vector**: Pure vector similarity is giving way to graph-based relational memory (Zep/Graphiti leading)
3. **Temporal awareness**: When something was learned matters as much as what was learned
4. **Memory evaluation**: Growing need for standardized benchmarks (MemBench, LOCOMO)
5. **Neuroscience inspiration deepening**: Moving beyond simple analogy to implementing consolidation, interference, emotional tagging
6. **Multi-modal memory**: Agents remembering images, code, structured data — not just text
7. **Production hardening**: Research moving toward deployable systems (Mem0, Letta, Zep all have cloud offerings)

---

## Open Research Problems

1. **Memory hallucination**: Agents "remembering" things that never happened
2. **Scalability**: How to manage millions of memories efficiently
3. **Privacy & forgetting**: Right to be forgotten, selective memory deletion
4. **Cross-agent memory transfer**: How to share memories between different agents safely
5. **Memory evaluation**: No agreed-upon benchmarks for memory quality
6. **Optimal memory lifecycle**: When to consolidate, when to forget, when to abstract
7. **Grounding**: Ensuring memories accurately reflect reality vs. agent interpretation
8. **Cost-efficiency**: Reducing LLM calls needed for memory management

---

## Implications for Hippocampus

The name "hippocampus" is perfect — the biological hippocampus is the brain's memory consolidation center. Our project should embrace this metaphor:

1. **Implement true consolidation**: Short-term → long-term transfer with importance-based filtering (no existing project does this well)
2. **Support all CoALA memory types**: Episodic + semantic + procedural (Voyager's skill library is the best procedural memory example)
3. **Adopt Generative Agents' retrieval formula** as baseline: recency × importance × relevance
4. **Learn from MemGPT/Letta**: Agent-driven memory management is the winning paradigm
5. **Incorporate Zep/Graphiti's temporal model**: Time-aware memory is a clear differentiator
6. **Add what nobody has**: Memory decay, consolidation cycles, interference handling, emotional tagging
