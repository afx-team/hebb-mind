---
layout: home

hero:
  name: Hippocampus
  text: Agent 记忆框架
  tagline: 为你的 AI Agent 提供类脑记忆系统 — 自动巩固、检索与遗忘。
  actions:
    - theme: brand
      text: 快速开始
      link: /zh/quick-start
    - theme: alt
      text: GitHub 仓库
      link: https://github.com/afx-team/hippocampus

features:
  - icon: 🧠
    title: 记忆巩固
    details: 自动将记忆分类到语义、情景、偏好、程序性分区 — 模拟人类大脑的记忆系统。
  - icon: 🔄
    title: 动态遗忘
    details: 基于艾宾浩斯遗忘曲线的 TTL 公式 — 频繁访问的高重要性记忆存活更久，被忽略的自然消失。
  - icon: 🔍
    title: 混合检索
    details: 三路并行检索（向量 + 关键词 + 知识图谱），结合时效性、重要性、相关性三维评分。
  - icon: 🕸️
    title: 知识图谱
    details: 巩固过程中自动提取标签构建概念图谱，在 Web 控制台中可视化探索关系。
  - icon: ⚡
    title: 零配置启动
    details: "SQLite 后端：hippocampus init && hippocampus start 即可运行。生产环境可切换 PostgreSQL。"
  - icon: 🖥️
    title: Web 控制台
    details: 内置暗色主题管理面板，支持记忆 CRUD、语义搜索、分区管理、图谱可视化。
---

<div class="hippo-home">

<!-- ─────────────── Quick Install ─────────────── -->
<div class="hippo-install">
  <div class="hippo-install-label">10 秒安装</div>
  <div class="hippo-install-cmd">
    <code>pip install afx-hippocampus && hippocampus init && hippocampus start</code>
    <button class="hippo-copy" onclick="navigator.clipboard.writeText('pip install afx-hippocampus && hippocampus init && hippocampus start');this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><polyline points=&quot;20 6 9 17 4 12&quot;/></svg>';setTimeout(()=>{this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><rect x=&quot;9&quot; y=&quot;9&quot; width=&quot;13&quot; height=&quot;13&quot; rx=&quot;2&quot;/><path d=&quot;M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1&quot;/></svg>'},1200)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
  </div>
  <div class="hippo-install-hint">打开 <a href="http://localhost:8321/">http://localhost:8321/</a> — 就这么简单。</div>
</div>

<!-- ─────────────── Memory Lifecycle ─────────────── -->
<div class="hippo-section">
<h2>工作原理</h2>
<p class="hippo-section-sub">记忆流经四个阶段 — 如同人类海马体。</p>

<div class="hippo-lifecycle">
  <div class="hippo-stage">
    <div class="hippo-stage-icon">📥</div>
    <div class="hippo-stage-name">写入</div>
    <div class="hippo-stage-desc">新记忆进入工作记忆收件箱</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🧠</div>
    <div class="hippo-stage-name">巩固</div>
    <div class="hippo-stage-desc">代理分类到分区、提取标签</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🔍</div>
    <div class="hippo-stage-name">检索</div>
    <div class="hippo-stage-desc">三路混合搜索 + 多维评分</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💨</div>
    <div class="hippo-stage-name">遗忘</div>
    <div class="hippo-stage-desc">动态 TTL — 常用存活，忽略消退</div>
  </div>
</div>
</div>

<!-- ─────────────── Partitions ─────────────── -->
<div class="hippo-section">
<h2>类脑分区</h2>
<p class="hippo-section-sub">记忆自动归入神经科学启发的分类体系。</p>

<div class="hippo-partitions">
  <div class="hippo-partition" style="--part-color: #52b788; --part-bg: #1b4332;">
    <div class="hippo-partition-icon">📚</div>
    <div class="hippo-partition-name">语义</div>
    <div class="hippo-partition-desc">知识 / 事实</div>
  </div>
  <div class="hippo-partition" style="--part-color: #c77dff; --part-bg: #3c1642;">
    <div class="hippo-partition-icon">🎬</div>
    <div class="hippo-partition-name">情景</div>
    <div class="hippo-partition-desc">经历 / 事件</div>
  </div>
  <div class="hippo-partition" style="--part-color: #ff6b6b; --part-bg: #6b2d5b;">
    <div class="hippo-partition-icon">❤️</div>
    <div class="hippo-partition-name">偏好</div>
    <div class="hippo-partition-desc">喜好 / 厌恶</div>
  </div>
  <div class="hippo-partition" style="--part-color: #4ecdc4; --part-bg: #2d3a4a;">
    <div class="hippo-partition-icon">🔧</div>
    <div class="hippo-partition-name">程序性</div>
    <div class="hippo-partition-desc">技能 / 方法</div>
  </div>
</div>
</div>

<!-- ─────────────── Architecture ─────────────── -->
<div class="hippo-section">
<h2>架构</h2>

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
    <span class="hippo-arch-core-sub">工作记忆收件箱 · 巩固代理</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-row">
    <span class="hippo-arch-chip">混合检索</span>
    <span class="hippo-arch-chip">知识图谱</span>
    <span class="hippo-arch-chip">动态遗忘</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-row">
    <span class="hippo-arch-chip" style="--chip-color: #52b788; --chip-bg: #1b4332;">语义</span>
    <span class="hippo-arch-chip" style="--chip-color: #c77dff; --chip-bg: #3c1642;">情景</span>
    <span class="hippo-arch-chip" style="--chip-color: #ff6b6b; --chip-bg: #6b2d5b;">偏好</span>
    <span class="hippo-arch-chip" style="--chip-color: #4ecdc4; --chip-bg: #2d3a4a;">程序性</span>
    <span class="hippo-arch-chip" style="--chip-color: #aaa; --chip-bg: #3d3d3d;">自定义</span>
  </div>
</div>
</div>

<!-- ─────────────── Comparison ─────────────── -->
<div class="hippo-section hippo-section-compare">
<h2>为什么选 Hippocampus</h2>
<p class="hippo-section-sub">核心能力不落后 — 独特优势更突出。</p>

<div class="hippo-compare">
  <div class="hippo-compare-table">
    <table>
      <thead>
        <tr><th>特性</th><th>Mem0</th><th>Letta</th><th>Zep</th><th class="hippo-highlight">Hippocampus</th></tr>
      </thead>
      <tbody>
        <tr><td>多模型支持</td><td class="hippo-yes">✓</td><td class="hippo-yes">✓</td><td class="hippo-yes">✓</td><td class="hippo-highlight">通过 LiteLLM</td></tr>
        <tr><td>知识图谱</td><td class="hippo-partial">部分</td><td class="hippo-no">✗</td><td class="hippo-yes">✓</td><td class="hippo-highlight">标签图谱</td></tr>
        <tr><td>Web 管理界面</td><td class="hippo-yes">✓</td><td class="hippo-partial">仅云端</td><td class="hippo-partial">仅云端</td><td class="hippo-highlight">内置 SPA</td></tr>
        <tr><td>MCP Server</td><td class="hippo-yes">✓</td><td class="hippo-no">仅消费端</td><td class="hippo-yes">✓</td><td class="hippo-highlight">内置，自动启动</td></tr>
        <tr class="hippo-divider-row"><td colspan="5"></td></tr>
        <tr><td>记忆巩固</td><td class="hippo-partial">仅追加</td><td class="hippo-partial">休眠代理</td><td class="hippo-partial">矛盾解决</td><td class="hippo-highlight">自动 + 冲突解决</td></tr>
        <tr><td>遗忘/衰减</td><td class="hippo-no">✗</td><td class="hippo-no">✗</td><td class="hippo-partial">时序失效</td><td class="hippo-highlight">动态 TTL</td></tr>
        <tr><td>零配置部署</td><td class="hippo-no">需 API Key</td><td class="hippo-no">需 API Key + DB</td><td class="hippo-no">需 Postgres + Neo4j</td><td class="hippo-highlight">SQLite + 本地嵌入</td></tr>
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