---
layout: home

hero:
  name: Hippocampus
  text: Agent Memory Framework
  tagline: Give your AI agents a real memory — neuroscience-inspired consolidation, retrieval, and forgetting.
  actions:
    - theme: brand
      text: Get Started
      link: /quick-start
    - theme: alt
      text: View on GitHub
      link: https://github.com/afx-team/hippocampus

features:
  - icon: 🧠
    title: Memory Consolidation
    details: Automatic agent classifies memories into semantic, episodic, preference, and procedural partitions — just like the human brain.
  - icon: 🔄
    title: Dynamic Forgetting
    details: TTL formula inspired by Ebbinghaus — frequently accessed, high-importance memories live longer. Neglected memories fade naturally.
  - icon: 🔍
    title: Hybrid Search
    details: Three-path retrieval (vector + keyword + knowledge graph) with recency, importance, and relevance scoring.
  - icon: 🕸️
    title: Knowledge Graph
    details: Tags extracted during consolidation form a graph of connected concepts. Explore relationships visually in the Web Console.
  - icon: ⚡
    title: Zero-Config Start
    details: "SQLite backend: hippocampus init && hippocampus start is all you need. Upgrade to PostgreSQL for production."
  - icon: 🖥️
    title: Web Console
    details: Built-in dark-themed dashboard for memory CRUD, semantic search, partition management, and graph visualization.
---

<div class="hippo-home">

<!-- ─────────────── Quick Install ─────────────── -->
<div class="hippo-install">
  <div class="hippo-install-label">Install in 10 seconds</div>
  <div class="hippo-install-cmd">
    <code>pip install afx-hippocampus && hippocampus init && hippocampus start</code>
    <button class="hippo-copy" onclick="navigator.clipboard.writeText('pip install afx-hippocampus && hippocampus init && hippocampus start');this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><polyline points=&quot;20 6 9 17 4 12&quot;/></svg>';setTimeout(()=>{this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><rect x=&quot;9&quot; y=&quot;9&quot; width=&quot;13&quot; height=&quot;13&quot; rx=&quot;2&quot;/><path d=&quot;M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1&quot;/></svg>'},1200)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
  </div>
  <div class="hippo-install-hint">Open <a href="http://localhost:8321/">http://localhost:8321/</a> — that's it.</div>
</div>

<!-- ─────────────── Memory Lifecycle ─────────────── -->
<div class="hippo-section">
<h2>How It Works</h2>
<p class="hippo-section-sub">Memories flow through four stages — just like the human hippocampus.</p>

<div class="hippo-lifecycle">
  <div class="hippo-stage">
    <div class="hippo-stage-icon">📥</div>
    <div class="hippo-stage-name">Ingest</div>
    <div class="hippo-stage-desc">New memories land in the working memory inbox</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🧠</div>
    <div class="hippo-stage-name">Consolidate</div>
    <div class="hippo-stage-desc">Agent classifies into partitions, extracts tags</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🔍</div>
    <div class="hippo-stage-name">Retrieve</div>
    <div class="hippo-stage-desc">Three-path hybrid search with scoring</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💨</div>
    <div class="hippo-stage-name">Forget</div>
    <div class="hippo-stage-desc">Dynamic TTL — used memories live, neglected fade</div>
  </div>
</div>
</div>

<!-- ─────────────── Partitions ─────────────── -->
<div class="hippo-section">
<h2>Brain-Inspired Partitions</h2>
<p class="hippo-section-sub">Memories are automatically sorted into neuroscience-based categories.</p>

<div class="hippo-partitions">
  <div class="hippo-partition" style="--part-color: #52b788; --part-bg: #1b4332;">
    <div class="hippo-partition-icon">📚</div>
    <div class="hippo-partition-name">Semantic</div>
    <div class="hippo-partition-desc">Facts & Knowledge</div>
  </div>
  <div class="hippo-partition" style="--part-color: #c77dff; --part-bg: #3c1642;">
    <div class="hippo-partition-icon">🎬</div>
    <div class="hippo-partition-name">Episodic</div>
    <div class="hippo-partition-desc">Events & History</div>
  </div>
  <div class="hippo-partition" style="--part-color: #ff6b6b; --part-bg: #6b2d5b;">
    <div class="hippo-partition-icon">❤️</div>
    <div class="hippo-partition-name">Preference</div>
    <div class="hippo-partition-desc">Likes & Dislikes</div>
  </div>
  <div class="hippo-partition" style="--part-color: #4ecdc4; --part-bg: #2d3a4a;">
    <div class="hippo-partition-icon">🔧</div>
    <div class="hippo-partition-name">Procedural</div>
    <div class="hippo-partition-desc">Skills & How-to</div>
  </div>
</div>
</div>

<!-- ─────────────── Architecture ─────────────── -->
<div class="hippo-section">
<h2>Architecture</h2>

<div class="hippo-arch">
  <div class="hippo-arch-row">
    <span class="hippo-arch-chip">API</span>
    <span class="hippo-arch-chip">MCP</span>
    <span class="hippo-arch-chip">CLI</span>
    <span class="hippo-arch-chip">Web Console</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-core">
    <span class="hippo-arch-core-label">HIPPOCAMPUS</span>
    <span class="hippo-arch-core-sub">Working Memory Inbox · Consolidation Agent</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-row">
    <span class="hippo-arch-chip">Hybrid Retrieval</span>
    <span class="hippo-arch-chip">Knowledge Graph</span>
    <span class="hippo-arch-chip">Dynamic Forgetting</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-row">
    <span class="hippo-arch-chip" style="--chip-color: #52b788; --chip-bg: #1b4332;">Semantic</span>
    <span class="hippo-arch-chip" style="--chip-color: #c77dff; --chip-bg: #3c1642;">Episodic</span>
    <span class="hippo-arch-chip" style="--chip-color: #ff6b6b; --chip-bg: #6b2d5b;">Preference</span>
    <span class="hippo-arch-chip" style="--chip-color: #4ecdc4; --chip-bg: #2d3a4a;">Procedural</span>
    <span class="hippo-arch-chip" style="--chip-color: #aaa; --chip-bg: #3d3d3d;">Custom</span>
  </div>
</div>
</div>

<!-- ─────────────── Comparison ─────────────── -->
<div class="hippo-section hippo-section-compare">
<h2>Why Hippocampus</h2>
<p class="hippo-section-sub">Core capabilities you'd expect — plus what only we do.</p>

<div class="hippo-compare">
  <div class="hippo-compare-table">
    <table>
      <thead>
        <tr><th>Feature</th><th>Mem0</th><th>Letta</th><th>Zep</th><th class="hippo-highlight">Hippocampus</th></tr>
      </thead>
      <tbody>
        <tr><td>Multi-model support</td><td class="hippo-yes">Yes</td><td class="hippo-yes">Yes</td><td class="hippo-yes">Yes</td><td class="hippo-highlight">Via LiteLLM</td></tr>
        <tr><td>Knowledge graph</td><td class="hippo-partial">Partial</td><td class="hippo-no">No</td><td class="hippo-yes">Yes</td><td class="hippo-highlight">Tag-based</td></tr>
        <tr><td>Web management UI</td><td class="hippo-yes">Yes</td><td class="hippo-partial">Cloud only</td><td class="hippo-partial">Cloud only</td><td class="hippo-highlight">Built-in SPA</td></tr>
        <tr><td>MCP Server</td><td class="hippo-yes">Yes</td><td class="hippo-no">Consumer only</td><td class="hippo-yes">Yes</td><td class="hippo-highlight">Built-in, auto-start</td></tr>
        <tr class="hippo-divider-row"><td colspan="5"></td></tr>
        <tr><td>Memory consolidation</td><td class="hippo-partial">ADD-only</td><td class="hippo-partial">Sleeptime Agent</td><td class="hippo-partial">Contradiction resolve</td><td class="hippo-highlight">Automatic + conflict resolve</td></tr>
        <tr><td>Forgetting / decay</td><td class="hippo-no">No</td><td class="hippo-no">No</td><td class="hippo-partial">Temporal invalidation</td><td class="hippo-highlight">Dynamic TTL</td></tr>
        <tr><td>Zero-config deploy</td><td class="hippo-no">API key required</td><td class="hippo-no">API key + DB</td><td class="hippo-no">Postgres + Neo4j</td><td class="hippo-highlight">SQLite + local embed</td></tr>
      </tbody>
    </table>
  </div>
</div>
</div>

</div>

<style>
.hippo-home { max-width: 1100px; margin: 0 auto; padding: 0 32px 80px; }

/* ── Install banner ── */
.hippo-install {
  text-align: center;
  margin: 48px 0 64px;
  padding: 28px 32px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(88,166,255,0.08) 0%, rgba(188,140,255,0.08) 100%);
  border: 1px solid rgba(124,106,246,0.2);
}
.hippo-install-label { font-size: 13px; color: var(--vp-c-text-2); margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1.5px; }
.hippo-install-cmd { margin: 12px 0; display: inline-flex; align-items: center; gap: 8px; justify-content: center; }
.hippo-install-cmd code {
  font-size: 15px; padding: 12px 20px; border-radius: 8px;
  background: var(--vp-c-bg-alt); border: 1px solid rgba(124,106,246,0.25);
  font-family: var(--vp-font-family-mono); color: var(--vp-c-brand-1);
  display: inline-block;
}
.hippo-copy {
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);
  border-radius: 6px; cursor: pointer; font-size: 14px;
  padding: 8px 8px; opacity: 0.5;
  transition: opacity 0.2s, border-color 0.2s;
}
.hippo-copy:hover { opacity: 1; border-color: var(--vp-c-brand-1); }
.hippo-install-hint { font-size: 13px; color: var(--vp-c-text-3); margin-top: 12px; }
.hippo-install-hint a { color: var(--vp-c-brand-1); text-decoration: underline; }

/* ── Sections ── */
.hippo-section { margin: 64px 0; }
.hippo-section h2 { text-align: center; margin-bottom: 8px; }
.hippo-section-sub { text-align: center; color: var(--vp-c-text-2); margin-bottom: 36px; font-size: 15px; }

/* ── Lifecycle flow ── */
.hippo-lifecycle {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; flex-wrap: wrap;
}
.hippo-stage {
  text-align: center; padding: 24px 20px; border-radius: 12px;
  background: var(--vp-c-bg-soft);
  flex: 1; min-width: 160px; max-width: 220px;
  transition: transform 0.25s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.hippo-stage:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
.hippo-stage-icon { font-size: 28px; margin-bottom: 8px; }
.hippo-stage-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.hippo-stage-desc { font-size: 13px; color: var(--vp-c-text-3); line-height: 1.4; }
.hippo-arrow { color: var(--vp-c-brand-1); font-size: 20px; font-weight: 700; }

/* ── Partitions grid ── */
.hippo-partitions {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.hippo-partition {
  text-align: center; padding: 28px 24px; border-radius: 12px;
  background: var(--part-bg); border: 1px solid rgba(255,255,255,0.06);
  transition: transform 0.25s, box-shadow 0.25s;
}
.hippo-partition:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
.hippo-partition-icon { font-size: 32px; margin-bottom: 10px; }
.hippo-partition-name { font-weight: 700; font-size: 16px; color: var(--part-color); margin-bottom: 4px; }
.hippo-partition-desc { font-size: 13px; color: rgba(255,255,255,0.55); }

/* ── Architecture diagram ── */
.hippo-arch {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.hippo-arch-row {
  display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
}
.hippo-arch-chip {
  padding: 6px 16px; border-radius: 6px; font-size: 13px; font-weight: 500;
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);
  color: var(--chip-color, var(--vp-c-text-1));
  white-space: nowrap;
}
.hippo-arch-chip[style*="--chip-bg"] {
  background: var(--chip-bg); border-color: rgba(255,255,255,0.06);
}
.hippo-arch-connector { color: var(--vp-c-text-3); font-size: 16px; }
.hippo-arch-core {
  text-align: center; padding: 16px 32px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(88,166,255,0.12) 0%, rgba(188,140,255,0.12) 100%);
  border: 1px solid rgba(124,106,246,0.3);
}
.hippo-arch-core-label {
  display: block; font-size: 18px; font-weight: 700;
  background: linear-gradient(135deg, #58a6ff, #bc8cff);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hippo-arch-core-sub { display: block; font-size: 13px; color: var(--vp-c-text-3); margin-top: 4px; }

/* ── Comparison table ── */
.hippo-section-compare { margin-bottom: 24px; }
.hippo-compare { display: flex; justify-content: center; }
.hippo-compare-table { overflow-x: auto; }
.hippo-compare-table table { width: auto; border-collapse: collapse; font-size: 14px; }
.hippo-compare-table th, .hippo-compare-table td {
  padding: 12px 20px; text-align: center;
}
.hippo-compare-table thead tr { border-bottom: 2px solid var(--vp-c-divider); }
.hippo-compare-table tbody tr + tr { border-top: 1px solid var(--vp-c-divider); }
.hippo-compare-table th:first-child, .hippo-compare-table td:first-child { text-align: left; font-weight: 500; }
.hippo-compare-table th { font-weight: 600; color: var(--vp-c-text-2); }
.hippo-highlight {
  color: var(--vp-c-brand-1); font-weight: 600;
  background: rgba(124,106,246,0.06);
}
.hippo-compare-table td:not(:first-child):not(.hippo-highlight):not(.hippo-yes):not(.hippo-no):not(.hippo-partial) { color: var(--vp-c-text-3); }
.hippo-yes { color: var(--vp-c-green-1); font-weight: 500; }
.hippo-no { color: var(--vp-c-text-3); font-weight: 400; }
.hippo-partial { color: var(--vp-c-yellow-1); font-weight: 500; }
.hippo-divider-row td { padding: 4px 0; border: none; }
.hippo-divider-row td::after { content: ''; display: block; border-top: 1px dashed var(--vp-c-divider); }

/* ── Responsive ── */
@media (max-width: 640px) {
  .hippo-lifecycle { flex-direction: column; }
  .hippo-arrow { transform: rotate(90deg); }
  .hippo-stage { max-width: 100%; }
}
</style>