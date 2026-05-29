---
layout: home

hero:
  name: Hebb Mind
  text: 脑子越用越灵光
  tagline: '一套受神经科学启发的 AI Agent 记忆框架'
  actions:
    - theme: brand
      text: 60 秒上手
      link: /zh/quick-start
    - theme: alt
      text: GitHub 仓库
      link: https://github.com/afx-team/hebb-mind
    - theme: alt
      text: Benchmarks
      link: /zh/benchmarks

features:
  - icon: ⚡
    title: 60 秒本地启动
    details: "pipx install + hebb setup + hebb service install。SQLite + sentence-transformers，零外部服务。写入与混合检索完全不依赖 API Key。"
  - icon: 🧠
    title: 巩固时解决冲突
    details: 巩固代理会合并重复、覆盖过时事实，而非简单追加。通过 LiteLLM 接入任意 LLM（OpenAI / Claude / 通义千问 / GLM / Kimi …）。
  - icon: 🔄
    title: 真正的遗忘
    details: "TTL = base × (1 + log(访问次数)) × 重要度 × exp(-衰减率 × 天数)。常用记忆存活，被忽略的自然消退，参数可按工作区调优。"
  - icon: 🔍
    title: 三路混合检索
    details: 向量 + 关键词 + 标签图谱并行检索，结合时效 / 重要性 / 相关性评分。基于 NetworkX 的知识图谱，支持沿邻居 API 游走。
  - icon: 🖥️
    title: 内置 Web 控制台
    details: 单页应用，覆盖记忆 CRUD、检索、分区、图谱视图。直接位于 http://localhost:8321/，无需另行部署。
  - icon: 🔌
    title: REST + MCP + Claude Code Hooks
    details: 三行命令为 Claude Code 启用跨会话记忆；hebb codex install 一键将能力以 MCP 工具形式接入 Codex。REST 文档位于 /docs。
---

<div class="hippo-home">

<!-- ─────────────── 赫布学习 ─────────────── -->
<div class="hippo-section">
<h2>为什么叫 "Hebb Mind"？</h2>
<p class="hippo-section-sub">1949 年，加拿大心理学家 <strong>唐纳德·O·赫布（Donald O. Hebb，1904–1985）</strong> 描述了大脑学习所遵循的法则。Hebb Mind 正建立在它之上。</p>

<div style="max-width:720px;margin:0 auto;padding:22px 28px;border-left:3px solid var(--vp-c-brand-1);background:var(--vp-c-bg-soft);border-radius:0 10px 10px 0;font-size:15px;line-height:1.7;color:var(--vp-c-text-2);font-style:italic;">
“当细胞 A 的轴突……反复或持续地参与激发细胞 B……A 作为激发 B 的细胞之一，其效率就会提高。”
<span style="display:block;margin-top:10px;font-size:13px;color:var(--vp-c-text-3);font-style:normal;">—— D. O. Hebb，《行为的组织》（1949）· 后世记为 <strong>"一起放电的神经元，会连到一起"</strong>。</span>
</div>

<p class="hippo-section-sub" style="margin-top:28px;">赫布的洞见：记忆不是一个"存放的地点"，而是一种"连接的模式"。共同出现的概念会连成<strong>细胞集群（cell assembly）</strong>，激活一部分便唤回全部。Hebb Mind 的标签知识图谱跑的正是这个回路。</p>

<div class="hippo-lifecycle">
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🔗</div>
    <div class="hippo-stage-name">连线</div>
    <div class="hippo-stage-desc">共同出现的标签建立图谱连边 —— 一个细胞集群</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💪</div>
    <div class="hippo-stage-name">强化</div>
    <div class="hippo-stage-desc">每次共现都加粗连边；巩固保留被反复强化的部分</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🌐</div>
    <div class="hippo-stage-name">补全</div>
    <div class="hippo-stage-desc">检索沿连边游走 —— 一个线索唤回整个模式</div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💨</div>
    <div class="hippo-stage-name">修剪</div>
    <div class="hippo-stage-desc">从不被共同激活的连接逐渐减弱、消退</div>
  </div>
</div>

<p class="hippo-section-sub" style="margin-top:28px;">那么<strong>海马体（hippocampus）</strong> —— 项目最初的名字呢？它作为工作记忆分区的名字（<code>mem_hippocampus</code>）保留了下来：每条新记忆在巩固前最先落入的收件箱。这正对应大脑的真实分工 —— 海马体正是把新经验暂存、再固化进长期皮层记忆的"门户"。大脑的<em>结构</em>成了一个组件，而<em>学习法则</em>成了项目的名字。</p>
</div>

<!-- ─────────────── Memory Lifecycle ─────────────── -->
<div class="hippo-section">
<h2>记忆回路</h2>
<p class="hippo-section-sub">四个阶段，按大脑大致相同的顺序运行 —— CA1 编码当下、慢波睡眠中的尖波涟漪进行回放（Wilson &amp; McNaughton, <em>Science</em>, 1994）、CA3 凭线索补全完整记忆、遗忘曲线（Ebbinghaus, 1885）安静地完成它的修剪。</p>

<div class="hippo-lifecycle">
  <div class="hippo-stage">
    <div class="hippo-stage-icon">📥</div>
    <div class="hippo-stage-name">编码</div>
    <div class="hippo-stage-desc">工作记忆收件箱 <em>（CA1 捕捉）</em></div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🧠</div>
    <div class="hippo-stage-name">回放与巩固</div>
    <div class="hippo-stage-desc">代理合并、分类、提取标签 <em>（尖波涟漪）</em></div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">🔍</div>
    <div class="hippo-stage-name">检索</div>
    <div class="hippo-stage-desc">向量 + 关键词 + 图谱 <em>（模式补全）</em></div>
  </div>
  <div class="hippo-arrow">→</div>
  <div class="hippo-stage">
    <div class="hippo-stage-icon">💨</div>
    <div class="hippo-stage-name">遗忘</div>
    <div class="hippo-stage-desc">动态 TTL <em>（Ebbinghaus 衰减）</em></div>
  </div>
</div>

<!-- ─────────────── Quick Install ─────────────── -->
<div class="hippo-install">
  <div class="hippo-install-label">60 秒上手 — 无需 API Key</div>
  <div class="hippo-install-cmd">
    <code>pipx install hebb-mind && hebb setup && hebb service install</code>
    <button class="hippo-copy" onclick="navigator.clipboard.writeText('pipx install hebb-mind && hebb setup && hebb service install');this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><polyline points=&quot;20 6 9 17 4 12&quot;/></svg>';setTimeout(()=>{this.innerHTML='<svg xmlns=&quot;http://www.w3.org/2000/svg&quot; width=&quot;14&quot; height=&quot;14&quot; viewBox=&quot;0 0 24 24&quot; fill=&quot;none&quot; stroke=&quot;currentColor&quot; stroke-width=&quot;2&quot; stroke-linecap=&quot;round&quot; stroke-linejoin=&quot;round&quot;><rect x=&quot;9&quot; y=&quot;9&quot; width=&quot;13&quot; height=&quot;13&quot; rx=&quot;2&quot;/><path d=&quot;M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1&quot;/></svg>'},1200)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
  </div>
  <div class="hippo-install-hint">还没装 <code>pipx</code>？ <a href="/zh/guide/installation#如果还没装-pipx">一次性安装</a>（brew / apt / dnf / python -m pip）。然后打开 <a href="http://localhost:8321/">http://localhost:8321/</a>。需要 LLM 巩固时见 <a href="/zh/quick-start#路径-b-5-分钟-启用-llm-巩固">5 分钟路径</a>。</div>
</div>

<!-- TODO(asset): screenshot of /index.html web console with sample memories. Save as repo_pages/public/web-console-hero.png, then uncomment the block below. -->
<!--
<p style="text-align:center; margin: 32px 0 0;">
  <img src="/web-console-hero.png" alt="Hebb Mind Web 控制台 — 分区记忆与标签图谱" width="760" style="border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.18);">
</p>
-->

</div>

<!-- ─────────────── Architecture ─────────────── -->
<div class="hippo-section">
<h2>架构</h2>

<div class="hippo-arch">
  <div class="hippo-arch-layer-label">接口层</div>
  <div class="hippo-arch-row hippo-arch-row-stretch">
    <span class="hippo-arch-chip">REST API</span>
    <span class="hippo-arch-chip">MCP Server</span>
    <span class="hippo-arch-chip">CLI</span>
    <span class="hippo-arch-chip">Web Console</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-core">
    <span class="hippo-arch-core-label">HEBB MIND 核心</span>
    <span class="hippo-arch-core-sub">工作记忆收件箱 · 巩固代理 · 回忆代理 (Agentic RAG) · 调度器</span>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-layer-label">处理引擎</div>
  <div class="hippo-arch-row">
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">混合检索</span>
      <span class="hippo-arch-chip-hint">向量 · 全文 · 图谱</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">知识图谱</span>
      <span class="hippo-arch-chip-hint">标签图谱 · NetworkX</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">评分引擎</span>
      <span class="hippo-arch-chip-hint">时效性 · 重要性 · 相关性</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip">动态遗忘</span>
      <span class="hippo-arch-chip-hint">艾宾浩斯 TTL 衰减</span>
    </div>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-layer-label">基础设施</div>
  <div class="hippo-arch-row">
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip" style="--chip-color: #58a6ff; --chip-bg: #1a3a5c;">存储</span>
      <span class="hippo-arch-chip-hint">SQLite + sqlite-vec · PostgreSQL + pgvector</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip" style="--chip-color: #58a6ff; --chip-bg: #1a3a5c;">嵌入</span>
      <span class="hippo-arch-chip-hint">本地 (sentence-transformers) · API</span>
    </div>
    <div class="hippo-arch-chip-stack">
      <span class="hippo-arch-chip" style="--chip-color: #58a6ff; --chip-bg: #1a3a5c;">LLM</span>
      <span class="hippo-arch-chip-hint">100+ 提供商 via LiteLLM</span>
    </div>
  </div>
  <div class="hippo-arch-connector">▼</div>
  <div class="hippo-arch-layer-label">记忆分区</div>
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
</div>

<!-- ─────────────── Comparison ─────────────── -->
<div class="hippo-section hippo-section-compare">
<h2>为什么选 Hebb Mind</h2>
<p class="hippo-section-sub">核心能力不落后 — 独特优势更突出。</p>

<div class="hippo-compare">
  <div class="hippo-compare-table">
    <table>
      <thead>
        <tr><th>特性</th><th>Mem0</th><th>Letta</th><th>Zep</th><th class="hippo-highlight">Hebb Mind</th></tr>
      </thead>
      <tbody>
        <tr><td>多模型支持</td><td class="hippo-yes">✓</td><td class="hippo-yes">✓</td><td class="hippo-yes">✓</td><td class="hippo-highlight">通过 LiteLLM</td></tr>
        <tr><td>知识图谱</td><td class="hippo-partial">可插拔（v3 已移除）</td><td class="hippo-no">✗</td><td class="hippo-yes">✓（Graphiti）</td><td class="hippo-highlight">标签图谱（NetworkX）</td></tr>
        <tr><td>自托管 Web UI</td><td class="hippo-partial">仅云端</td><td class="hippo-partial">仅云端</td><td class="hippo-partial">仅云端</td><td class="hippo-highlight">内置 SPA</td></tr>
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
.hippo-home { max-width: 1100px; margin: 0 auto; padding: 0 32px 0; }

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

/* ── Sections ── */
.hippo-section {
  margin: 0;
  display: flex; flex-direction: column; justify-content: center;
  padding: 72px 0; box-sizing: border-box;
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
  .hippo-home { padding: 0 20px 0; }
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
