---
layout: home

hero:
  name: Hippocampus
  text: Agent 记忆框架
  tagline: 为你的 AI Agent 提供类脑记忆系统 — 自动巩固、检索与遗忘。
  actions:
    - theme: brand
      text: 快速开始
      link: /zh/guide/getting-started
    - theme: alt
      text: GitHub 仓库
      link: https://github.com/afx-team/hippocampus

features:
  - icon: "\U0001F9E0"
    title: 记忆巩固
    details: 自动将记忆分类到语义、情景、偏好、程序性分区 — 模拟人类大脑的记忆系统。
  - icon: "\U0001F504"
    title: 动态遗忘
    details: 基于艾宾浩斯遗忘曲线的 TTL 公式 — 频繁访问的高重要性记忆存活更久，被忽略的自然消失。
  - icon: "\U0001F50D"
    title: 混合检索
    details: 三路并行检索（向量 + 关键词 + 知识图谱），结合时效性、重要性、相关性三维评分。
  - icon: "\U0001F310"
    title: 知识图谱
    details: 巩固过程中自动提取标签构建概念图谱，在 Web 控制台中可视化探索关系。
  - icon: "\u26A1"
    title: 零配置启动
    details: "SQLite 后端：hippocampus init && hippocampus start 即可运行。生产环境可切换 PostgreSQL。"
  - icon: "\U0001F5A5"
    title: Web 控制台
    details: 内置暗色主题管理面板，支持记忆 CRUD、语义搜索、分区管理、图谱可视化。
---

<div class="vp-doc" style="max-width: 780px; margin: 48px auto; padding: 0 24px;">

## 快速安装

```bash
pip install afx-hippocampus
hippocampus init
hippocampus start
# 打开 http://localhost:8321/
```

## 架构

<table style="width:100%; border:none; border-collapse:collapse;">
<tr>
<td align="center" colspan="5" style="padding:6px 14px; background:#1a1a2e; border-radius:8px; color:#e0e0e0; font-weight:600;">
API &middot; MCP &middot; CLI
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:18px; color:#555;">▼</td></tr>
<tr>
<td align="center" colspan="5" style="padding:10px 18px; background:#16213e; border-radius:8px;">
<b style="color:#00d2ff; font-size:16px;">HIPPOCAMPUS</b><br/>
<span style="color:#888; font-size:12px;">工作记忆收件箱</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; color:#555; padding:4px 0;">▼&nbsp; 巩固代理 <span style="color:#666; font-size:11px;">(Agentic RAG &middot; 分类 &middot; 冲突解决 &middot; 标签提取)</span></td></tr>
<tr>
<td align="center" style="padding:8px 12px; background:#1b4332; border-radius:6px; min-width:100px;">
<b style="color:#52b788;">语义</b><br/><span style="color:#888; font-size:11px;">知识/事实</span>
</td>
<td align="center" style="padding:8px 12px; background:#3c1642; border-radius:6px; min-width:100px;">
<b style="color:#c77dff;">情景</b><br/><span style="color:#888; font-size:11px;">经历/事件</span>
</td>
<td align="center" style="padding:8px 12px; background:#6b2d5b; border-radius:6px; min-width:100px;">
<b style="color:#ff6b6b;">偏好</b><br/><span style="color:#888; font-size:11px;">喜好/厌恶</span>
</td>
<td align="center" style="padding:8px 12px; background:#2d3a4a; border-radius:6px; min-width:100px;">
<b style="color:#4ecdc4;">程序性</b><br/><span style="color:#888; font-size:11px;">技能/方法</span>
</td>
<td align="center" style="padding:8px 12px; background:#3d3d3d; border-radius:6px; min-width:100px;">
<b style="color:#aaa;">自定义</b><br/><span style="color:#888; font-size:11px;">你的分区</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; padding:6px 0;">
<span style="color:#555;">▼</span>&nbsp;
<span style="color:#666; font-size:12px;">混合检索</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">知识图谱</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">动态遗忘 (TTL)</span>
</td></tr>
</table>

## 对比

| 特性 | Mem0 | Letta | Zep | **Hippocampus** |
|------|------|-------|-----|-----------------|
| 记忆巩固 | - | - | - | 自动化 |
| 遗忘/衰减 | - | - | 隐式 | 动态 TTL |
| 知识图谱 | - | - | 部分 | 内置 |
| 零配置部署 | - | - | - | SQLite |
| 多模型支持 | 部分 | 部分 | 部分 | 通过 LiteLLM |
| Web 管理界面 | - | 部分 | 部分 | 内置 |

</div>