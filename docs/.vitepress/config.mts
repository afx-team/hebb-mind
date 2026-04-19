import { defineConfig } from 'vitepress'

const GITHUB_REPO = 'https://github.com/afx-team/hippocampus'

/* ---------- shared sidebar ---------- */
function guideSidebar(prefix = '') {
  return [
    {
      text: prefix ? '快速上手' : 'Getting Started',
      items: [
        { text: prefix ? '快速开始' : 'Quick Start', link: `${prefix}/guide/getting-started` },
        { text: prefix ? '安装' : 'Installation', link: `${prefix}/guide/installation` },
        { text: prefix ? '配置' : 'Configuration', link: `${prefix}/guide/configuration` },
        { text: 'Docker', link: `${prefix}/guide/docker` },
      ],
    },
    {
      text: prefix ? '核心概念' : 'Concepts',
      items: [
        { text: prefix ? '记忆生命周期' : 'Memory Lifecycle', link: `${prefix}/concepts/memory-lifecycle` },
        { text: prefix ? '记忆巩固' : 'Consolidation', link: `${prefix}/concepts/consolidation` },
        { text: prefix ? '动态遗忘' : 'Forgetting', link: `${prefix}/concepts/forgetting` },
        { text: prefix ? '知识图谱' : 'Knowledge Graph', link: `${prefix}/concepts/knowledge-graph` },
        { text: prefix ? '混合检索' : 'Hybrid Search', link: `${prefix}/concepts/hybrid-search` },
      ],
    },
    {
      text: 'API Reference',
      items: [
        { text: 'Memories', link: `${prefix}/api/memories` },
        { text: 'Search', link: `${prefix}/api/search` },
        { text: 'Partitions', link: `${prefix}/api/partitions` },
        { text: 'Knowledge Graph', link: `${prefix}/api/graph` },
        { text: 'Admin', link: `${prefix}/api/admin` },
        { text: 'Config', link: `${prefix}/api/config` },
      ],
    },
    {
      text: 'CLI',
      items: [
        { text: prefix ? 'CLI 命令' : 'CLI Reference', link: `${prefix}/cli/` },
      ],
    },
    {
      text: prefix ? '进阶' : 'Advanced',
      items: [
        { text: prefix ? '存储后端' : 'Storage Backends', link: `${prefix}/advanced/storage-backends` },
        { text: prefix ? '多模型支持' : 'Multi-model', link: `${prefix}/advanced/multi-model` },
        { text: 'MCP Integration', link: `${prefix}/advanced/mcp-integration` },
        { text: prefix ? '评估基准' : 'Evaluation', link: `${prefix}/advanced/evaluation` },
      ],
    },
    {
      text: prefix ? '开发' : 'Development',
      items: [
        { text: prefix ? '贡献指南' : 'Contributing', link: `${prefix}/development/contributing` },
        { text: 'Changelog', link: `${prefix}/development/changelog` },
        { text: prefix ? '路线图' : 'Roadmap', link: `${prefix}/development/roadmap` },
      ],
    },
    {
      text: prefix ? '研究' : 'Research',
      items: [
        { text: prefix ? '论文综述' : 'Papers Survey', link: `${prefix}/research/papers-survey` },
        { text: prefix ? '开源项目分析' : 'Open-source Analysis', link: `${prefix}/research/github-projects` },
      ],
    },
  ]
}

export default defineConfig({
  title: 'Hippocampus',
  description: 'Neuroscience-inspired memory framework for AI agents',

  /* GitHub Pages sub-path */
  base: '/hippocampus/',

  /* dark mode default */
  appearance: 'dark',

  /* localhost links are runtime references, not doc links */
  ignoreDeadLinks: [
    /localhost/,
    /\.\.\/papers\//,
    /\.\.\/analysis\//,
  ],

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/hippocampus/logo.svg' }],
  ],

  /* i18n */
  locales: {
    root: {
      label: 'English',
      lang: 'en',
      themeConfig: {
        nav: [
          { text: 'Guide', link: '/guide/getting-started' },
          { text: 'API', link: '/api/memories' },
          { text: 'CLI', link: '/cli/' },
        ],
        sidebar: guideSidebar(),
      },
    },
    zh: {
      label: '中文',
      lang: 'zh-CN',
      title: 'Hippocampus 海马体',
      description: '受神经科学启发的 AI Agent 记忆框架',
      themeConfig: {
        nav: [
          { text: '指南', link: '/zh/guide/getting-started' },
          { text: 'API', link: '/zh/api/memories' },
          { text: 'CLI', link: '/zh/cli/' },
        ],
        sidebar: { '/zh/': guideSidebar('/zh') },
        outline: { label: '本页目录' },
        docFooter: { prev: '上一页', next: '下一页' },
        lastUpdated: { text: '最后更新' },
        returnToTopLabel: '返回顶部',
        sidebarMenuLabel: '菜单',
        darkModeSwitchLabel: '主题',
      },
    },
  },

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'Hippocampus',

    socialLinks: [
      { icon: 'github', link: GITHUB_REPO },
    ],

    search: {
      provider: 'local',
    },

    editLink: {
      pattern: `${GITHUB_REPO}/edit/main/docs/:path`,
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the Apache-2.0 License.',
      copyright: 'Copyright 2026 afx-team',
    },
  },

  /* hide research raw markdown from sidebar (they are internal notes) */
  srcExclude: ['**/papers/**', '**/analysis/**', '**/design/**', '**/surveys/**'],
})
