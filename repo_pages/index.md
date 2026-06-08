---
layout: home

hero:
  name: Hebb Mind
  text: Memory that wires itself.
  tagline: 'A memory framework for AI agents — named for Donald Hebb, whose rule the brain learns by: neurons that fire together, wire together.'
  actions:
    - theme: brand
      text: Get Started in 60s
      link: /quick-start
    - theme: alt
      text: View on GitHub
      link: https://github.com/afx-team/hebb-mind
    - theme: alt
      text: Benchmarks
      link: /benchmarks

features:
  - icon: ⚡
    title: 60-second local start
    details: "pipx install + hebb setup + hebb service install. First run downloads a small embedding model (~90MB English / ~470MB multilingual), only if not already present. SQLite + sentence-transformers, zero external services. No API key needed for ingest and hybrid search."
  - icon: 🧠
    title: Conflict-resolving consolidation
    details: An agent merges duplicates and overwrites stale facts — not just append. Bring any LLM via LiteLLM (OpenAI, Claude, Qwen, GLM, Kimi, …).
  - icon: 🔄
    title: Honest forgetting
    details: "TTL = base × (1 + log(access)) × importance × exp(-decay × days). Frequently used memories survive; neglected ones decay. Tunable per workspace."
  - icon: 🔍
    title: Three-path hybrid search
    details: Vector + keyword + tag-graph retrieval, scored on recency, importance, and relevance. NetworkX-backed knowledge graph; explore neighbors via the API.
  - icon: 🖥️
    title: Built-in Web Console
    details: Single-page app for memory CRUD, search, partitions, and graph view. Lives at http://localhost:8321/ — no separate deploy.
  - icon: 🔌
    title: REST + MCP + Claude Code hooks
    details: Three-line install gives Claude Code cross-session memory; hebb codex install adds the same as MCP tools. REST docs at /docs.
---

<div class="hippo-home">

<!-- ─────────────── The Hebbian Idea ─────────────── -->
<div class="hippo-section">
<h2>Why "Hebb Mind"?</h2>
<p class="hippo-section-sub">In 1949, Canadian psychologist <strong>Donald O. Hebb</strong> (1904–1985) described the rule the brain learns by. Hebb Mind is built on it.</p>

<div class="hippo-hebb-quote">
“When an axon of cell A … repeatedly or persistently takes part in firing cell B, … A's efficiency, as one of the cells firing B, is increased.”
<span>— D. O. Hebb, <em>The Organization of Behavior</em> (1949) · remembered as <strong>“neurons that fire together, wire together.”</strong></span>
</div>

<p class="hippo-section-sub" style="margin-top:28px;">Hebb's insight: a memory is not a <em>place</em> — it is a <em>pattern of connection</em>. Concepts that co-occur wire into <strong>cell assemblies</strong>; a partial cue lights up the rest. Hebb Mind's tag knowledge graph runs exactly that loop.</p>

<div class="hippo-lifecycle">
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🔗</div>
    <div class="hippo-stage-name">Wire</div>
    <div class="hippo-stage-desc">Co-occurring tags gain a graph edge — a cell assembly</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💪</div>
    <div class="hippo-stage-name">Strengthen</div>
    <div class="hippo-stage-desc">Each co-activation thickens the edge; consolidation keeps what's reinforced</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🌐</div>
    <div class="hippo-stage-name">Complete</div>
    <div class="hippo-stage-desc">Retrieval walks the edges — a cue recalls the whole pattern</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💨</div>
    <div class="hippo-stage-name">Prune</div>
    <div class="hippo-stage-desc">What is never co-activated weakens and fades</div>
  </div>
</div>

<p class="hippo-section-sub" style="margin-top:28px;">And the <strong>hippocampus</strong> — the project's original name? It lives on as the working-memory partition (<code>mem_hippocampus</code>): the inbox every new memory enters before consolidation, just as the brain's hippocampus gates new experience into long-term memory. The brain <em>region</em> became one component; the <em>learning rule</em> became the name.</p>
</div>

<!-- ─────────────── Memory Lifecycle ─────────────── -->
<div class="hippo-section">
<h2>The Memory Loop</h2>
<p class="hippo-section-sub">Four stages, in roughly the order the brain runs them — encoding in CA1, replay during slow-wave sleep (Wilson &amp; McNaughton, <em>Science</em>, 1994), pattern-completion in CA3, and the forgetting curve (Ebbinghaus, 1885) doing its quiet work.</p>

<div class="hippo-lifecycle">
  <div class="hippo-stage">
    <div class="hippo-stage-icon">📥</div>
    <div class="hippo-stage-name">Encode</div>
    <div class="hippo-stage-desc">Working-memory inbox <em>(CA1 capture)</em></div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🧠</div>
    <div class="hippo-stage-name">Replay &amp; Consolidate</div>
    <div class="hippo-stage-desc">Agent merges, classifies, tags <em>(sharp-wave ripples)</em></div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🔍</div>
    <div class="hippo-stage-name">Retrieve</div>
    <div class="hippo-stage-desc">Vector + keyword + graph <em>(pattern completion)</em></div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💨</div>
    <div class="hippo-stage-name">Forget</div>
    <div class="hippo-stage-desc">Dynamic TTL <em>(Ebbinghaus decay)</em></div>
  </div>
</div>


<!-- ─────────────── Quick Install ─────────────── -->
<div class="hippo-install">
  <div class="hippo-install-label">60-second start — no API key</div>
  <div class="hippo-install-cmd">
    <code>pipx install hebb-mind && hebb setup && hebb service install</code>
    <button class="hippo-copy" onclick="navigator.clipboard.writeText('pipx install hebb-mind && hebb setup && hebb service install');this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><polyline points=&quot;20 6 9 17 4 12&quot;/></svg>';setTimeout(()=>{this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><rect x=&quot;9&quot; y=&quot;9&quot; width=&quot;13&quot; height=&quot;13&quot; rx=&quot;2&quot;/><path d=&quot;M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1&quot;/></svg>'},1200)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
  </div>
  <div class="hippo-install-hint">First run downloads a small embedding model (~90MB English / ~470MB multilingual), only if not already cached — about a minute on the English/<code>fast</code> path, a little longer for multilingual. Want the high-quality bge models (1–2GB)? Use <code>hebb setup --profile best</code>. No <code>pipx</code> yet? <a href="/guide/installation#install-pipx-if-you-don-t-have-it">One-time setup</a> (brew / apt / dnf / python -m pip). Then open <a href="http://localhost:8321/">http://localhost:8321/</a>. For LLM consolidation, see the <a href="/quick-start#path-b-5-minutes-with-llm-consolidation">5-minute path</a>.</div>
</div>

<!-- TODO(asset): screenshot of /index.html web console with sample memories. Save as repo_pages/public/web-console-hero.png, then uncomment the block below. -->
<!--
<p style="text-align:center; margin: 32px 0 0;">
  <img src="/web-console-hero.png" alt="Hebb Mind Web Console showing partitioned memories and tag graph" width="760" style="border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.18);">
</p>
-->
</div>

<!-- ─────────────── Architecture ─────────────── -->
<div class="hippo-section">
<h2>Architecture</h2>

<div class="hippo-arch">
  <div class="hippo-arch-layer-label">Interface Layer</div>
  <div class="hippo-arch-row hippo-arch-row-stretch">
    <span class="hippo-arch-chip">REST API</span>
    <span class="hippo-arch-chip">MCP Server</span>
    <span class="hippo-arch-chip">CLI</span>
    <span class="hippo-arch-chip">Web Console</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-core">
    <span class="hippo-arch-core-label">HEBB MIND CORE</span>
    <span class="hippo-arch-core-sub">Working Memory Inbox · Consolidation Agent · Recall Agent (Agentic RAG) · Scheduler</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-layer-label">Processing Engine</div>
  <div class="hippo-arch-row">
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">Hybrid Retrieval</span>
      <span class="hippo-arch-chip-hint">Vector · FTS · Graph</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">Knowledge Graph</span>
      <span class="hippo-arch-chip-hint">Tag-based · NetworkX</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">Scoring</span>
      <span class="hippo-arch-chip-hint">Recency · Importance · Relevance</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">Dynamic Forgetting</span>
      <span class="hippo-arch-chip-hint">Ebbinghaus TTL Decay</span>
    </div>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-layer-label">Infrastructure</div>
  <div class="hippo-arch-row">
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip" style="--chip-color: #58a6ff; --chip-bg: #1a3a5c;">Storage</span>
      <span class="hippo-arch-chip-hint">SQLite + sqlite-vec · PostgreSQL + pgvector</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip" style="--chip-color: #58a6ff; --chip-bg: #1a3a5c;">Embedding</span>
      <span class="hippo-arch-chip-hint">Local (sentence-transformers) · API</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip" style="--chip-color: #58a6ff; --chip-bg: #1a3a5c;">LLM</span>
      <span class="hippo-arch-chip-hint">100+ providers via LiteLLM</span>
    </div>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-layer-label">Memory Partitions</div>
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
</div>

<!-- ─────────────── Comparison ─────────────── -->
<div class="hippo-section hippo-section-compare">
<h2>Why Hebb Mind</h2>
<p class="hippo-section-sub">Core capabilities you'd expect — plus what only we do. </p>

<div class="hippo-compare">
  <div class="hippo-compare-table">
    <table>
      <thead>
        <tr><th>Feature</th><th>Mem0</th><th>Letta</th><th>Zep</th><th class="hippo-highlight">Hebb Mind</th></tr>
      </thead>
      <tbody>
        <tr><td>Multi-model support</td><td class="hippo-yes">Yes</td><td class="hippo-yes">Yes</td><td class="hippo-yes">Yes</td><td class="hippo-highlight">Via LiteLLM</td></tr>
        <tr><td>Knowledge graph</td><td class="hippo-partial">Pluggable (removed in v3)</td><td class="hippo-no">No</td><td class="hippo-yes">Yes (Graphiti)</td><td class="hippo-highlight">Tag-based (NetworkX)</td></tr>
        <tr><td>Self-hosted Web UI</td><td class="hippo-partial">Cloud only</td><td class="hippo-partial">Cloud only</td><td class="hippo-partial">Cloud only</td><td class="hippo-highlight">Built-in SPA</td></tr>
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
.hippo-home { max-width: 1100px; margin: 0 auto; padding: 0 32px 0; }

/* ── Fade-in animation ── */
@keyframes hippoFadeUp {
  from { opacity: 0; transform: translateY(40px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.hippo-section > * { opacity: 0; }
.hippo-section.is-visible > * {
  animation: hippoFadeUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
.hippo-section.is-visible > *:nth-child(1) { animation-delay: 0s; }
.hippo-section.is-visible > *:nth-child(2) { animation-delay: 0.12s; }
.hippo-section.is-visible > *:nth-child(3) { animation-delay: 0.24s; }
.hippo-section.is-visible > *:nth-child(4) { animation-delay: 0.36s; }

/* ── Install banner ── */
.hippo-install {
  text-align: center;
  margin: 48px 0 0;
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

/* ── Hebb quote ── */
.hippo-hebb-quote {
  max-width: 720px; margin: 0 auto; padding: 22px 28px;
  border-left: 3px solid var(--vp-c-brand-1);
  background: var(--vp-c-bg-soft); border-radius: 0 10px 10px 0;
  font-size: 15px; line-height: 1.7; color: var(--vp-c-text-2);
  font-style: italic;
}
.hippo-hebb-quote span {
  display: block; margin-top: 10px; font-size: 13px;
  color: var(--vp-c-text-3); font-style: normal;
}

/* ── Sections ── */
.hippo-section {
  margin: 0;
  display: flex; flex-direction: column; justify-content: center;
  padding: 72px 0; box-sizing: border-box;
}

/* ── Hero background video ── */
.VPHero { position: relative; overflow: hidden; isolation: isolate; }
.VPHero > .container { position: relative; z-index: 3; }
/* Fade the video's lower edge to transparent so it dissolves into the overlay/page */
.hippo-hero-bg {
  position: absolute; inset: 0; z-index: 0;
  width: 100%; height: 100%; object-fit: cover; object-position: center;
  pointer-events: none;
  filter: saturate(1.05) contrast(1.02);
  -webkit-mask-image: linear-gradient(180deg, #000 0%, #000 55%, rgba(0,0,0,0.6) 80%, transparent 100%);
          mask-image: linear-gradient(180deg, #000 0%, #000 55%, rgba(0,0,0,0.6) 80%, transparent 100%);
}
/* Overlay sits above the video and resolves to the exact page bg at the seam */
.hippo-hero-bg-overlay {
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background:
    radial-gradient(ellipse at 30% 35%, rgba(13,17,23,0.20) 0%, rgba(13,17,23,0.55) 70%),
    linear-gradient(180deg, rgba(13,17,23,0.25) 0%, rgba(13,17,23,0.55) 55%, var(--vp-c-bg) 100%);
}
/* Extra-soft bridge: a final wash glued to the bottom of the hero that matches page bg */
.VPHero::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 38%;
  z-index: 2; pointer-events: none;
  background: linear-gradient(180deg, transparent 0%, var(--vp-c-bg) 92%);
}
/* Lift hero text contrast against the moving background */
.VPHero .name, .VPHero .text { color: #fff !important; text-shadow: 0 2px 14px rgba(0,0,0,0.45); }
.VPHero .name .clip {
  background: linear-gradient(135deg, #c9b8ff 0%, #8ec1ff 100%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.VPHero .tagline { color: rgba(255,255,255,0.86) !important; text-shadow: 0 1px 8px rgba(0,0,0,0.4); }
@media (prefers-reduced-motion: reduce) {
  .hippo-hero-bg { display: none; }
}
.hippo-section h2 { text-align: center; margin-bottom: 8px; border-top: none; padding-top: 0; }
.hippo-section-sub { text-align: center; color: var(--vp-c-text-2); margin-bottom: 36px; font-size: 15px; }

/* ── Lifecycle flow ── */
.hippo-lifecycle {
  display: flex; align-items: stretch; justify-content: center;
  gap: 8px; flex-wrap: nowrap;
}
.hippo-stage {
  text-align: center; padding: 24px 16px; border-radius: 12px;
  background: var(--vp-c-bg-soft);
  flex: 1; min-width: 0;
  transition: transform 0.25s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.hippo-stage:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
.hippo-stage-icon { font-size: 28px; margin-bottom: 8px; }
.hippo-stage-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.hippo-stage-desc { font-size: 13px; color: var(--vp-c-text-3); line-height: 1.4; }
.hippo-arrow { color: var(--vp-c-brand-1); font-size: 20px; font-weight: 700; display: flex; align-items: center; flex-shrink: 0; }

/* ── Partitions grid ── */
.hippo-partitions {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 12px; width: 100%;
}
.hippo-partition {
  text-align: center; padding: 24px 16px; border-radius: 12px;
  background: var(--part-bg); border: 1px solid rgba(255,255,255,0.06);
  transition: transform 0.25s, box-shadow 0.25s;
}
.hippo-partition:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
.hippo-partition-icon { font-size: 28px; margin-bottom: 8px; }
.hippo-partition-name { font-weight: 700; font-size: 15px; color: var(--part-color); margin-bottom: 4px; }
.hippo-partition-desc { font-size: 12px; color: rgba(255,255,255,0.55); }

/* ── Architecture diagram ── */
.hippo-arch {
  display: flex; flex-direction: column; align-items: stretch; gap: 0;
}
.hippo-arch-row {
  display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;
  width: 100%;
}
.hippo-arch-chip {
  padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 500;
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);
  color: var(--chip-color, var(--vp-c-text-1));
  white-space: nowrap; text-align: center;
}
.hippo-arch-chip[style*="--chip-bg"] {
  background: var(--chip-bg); border-color: rgba(255,255,255,0.06);
}
.hippo-arch-connector { color: var(--vp-c-text-3); font-size: 14px; text-align: center; line-height: 1; padding: 2px 0; }
.hippo-arch-core {
  text-align: center; padding: 16px 32px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(88,166,255,0.12) 0%, rgba(188,140,255,0.12) 100%);
  border: 1px solid rgba(124,106,246,0.3);
  width: 100%;
}
.hippo-arch-core-label {
  display: block; font-size: 18px; font-weight: 700;
  background: linear-gradient(135deg, #58a6ff, #bc8cff);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hippo-arch-core-sub { display: block; font-size: 13px; color: var(--vp-c-text-3); margin-top: 4px; }
.hippo-arch-layer-label {
  font-size: 11px; color: var(--vp-c-text-3); text-transform: uppercase;
  letter-spacing: 1.5px; text-align: center; padding: 2px 0 4px;
}
.hippo-arch-chip-stack { display: flex; flex-direction: column; align-items: center; gap: 2px; flex: 1; min-width: 0; }
.hippo-arch-chip-stack .hippo-arch-chip { width: 100%; }
.hippo-arch-chip-hint { font-size: 11px; color: var(--vp-c-text-3); text-align: center; }
.hippo-arch-row-stretch { justify-content: stretch; }
.hippo-arch-row-stretch .hippo-arch-chip { flex: 1; text-align: center; white-space: nowrap; }

/* ── Comparison table ── */
/* last section no extra bottom */
.hippo-compare { display: flex; justify-content: center; }
.hippo-compare-table { overflow-x: auto; width: 100%; }
.hippo-compare-table table { display: table; width: 100%; border-collapse: collapse; font-size: 14px; }
.hippo-compare-table th, .hippo-compare-table td {
  padding: 12px 16px; text-align: center;
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
@media (max-width: 768px) {
  .hippo-home { padding: 0 20px 32px; }
  .hippo-lifecycle { flex-wrap: wrap; }
  .hippo-stage { min-width: calc(50% - 20px); flex: 1 1 calc(50% - 20px); }
  .hippo-arrow { display: none; }
  .hippo-partitions { grid-template-columns: repeat(2, 1fr); }
  .hippo-arch-chip-stack { min-width: calc(50% - 12px); flex: 1 1 calc(50% - 12px); }
  .hippo-arch-row-stretch .hippo-arch-chip { min-width: calc(50% - 12px); flex: 1 1 calc(50% - 12px); }
  .hippo-install-cmd { flex-wrap: wrap; justify-content: center; }
  .hippo-install-cmd code { font-size: 13px; padding: 10px 14px; word-break: break-all; white-space: normal; }
  .hippo-compare-table th, .hippo-compare-table td { padding: 10px 10px; font-size: 13px; }
}
@media (max-width: 480px) {
  .hippo-stage { min-width: 100%; }
  .hippo-partitions { grid-template-columns: repeat(2, 1fr); }
  .hippo-arch-chip-stack { min-width: 100%; }
  .hippo-arch-row-stretch .hippo-arch-chip { min-width: calc(50% - 12px); }
  .hippo-section { padding: 40px 0; }
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
  .hippo-section > * { opacity: 1; }
  .hippo-section.is-visible > * { animation: none; }
}
</style>

<script setup>
import { onMounted } from 'vue'
import { withBase } from 'vitepress'
onMounted(() => {
  // Inject background video into the VitePress hero
  const hero = document.querySelector('.VPHero')
  if (hero && !hero.querySelector('.hippo-hero-bg')) {
    const video = document.createElement('video')
    video.className = 'hippo-hero-bg'
    video.src = withBase('/home_video.mp4')
    video.autoplay = true
    video.muted = true
    video.loop = true
    video.playsInline = true
    video.setAttribute('aria-hidden', 'true')
    const overlay = document.createElement('div')
    overlay.className = 'hippo-hero-bg-overlay'
    hero.prepend(overlay)
    hero.prepend(video)
    // Some browsers need an explicit play() after the element is in the DOM
    const tryPlay = () => video.play().catch(() => {})
    tryPlay()
  }

  const sections = document.querySelectorAll('.hippo-section')
  if (!sections.length) return
  // Fade-in on scroll
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) e.target.classList.add('is-visible')
    })
  }, { threshold: 0.08, rootMargin: '0px 0px -60px 0px' })
  sections.forEach(s => io.observe(s))
})
</script>
