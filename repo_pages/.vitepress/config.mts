import { defineConfig } from 'vitepress'

const GITHUB_REPO = 'https://github.com/afx-team/hippocampus'

/* ---------- shared sidebar ---------- */
function guideSidebar(prefix = '') {
  return [
    {
      text: prefix ? '快速上手' : 'Quick Start',
      link: `${prefix}/quick-start`,
    },
    {
      text: prefix ? '指南' : 'Guide',
      items: [
        { text: prefix ? '安装' : 'Installation', link: `${prefix}/guide/installation` },
        { text: prefix ? '配置' : 'Configuration', link: `${prefix}/guide/configuration` },
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
        { text: 'CLI', link: `${prefix}/api/cli` },
      ],
    },
    {
      text: prefix ? '进阶' : 'Advanced',
      items: [
        { text: prefix ? '存储后端' : 'Storage Backends', link: `${prefix}/advanced/storage-backends` },
        { text: prefix ? '多模型支持' : 'Multi-model', link: `${prefix}/advanced/multi-model` },
        { text: 'MCP Integration', link: `${prefix}/advanced/mcp-integration` },
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
          { text: 'Quick Start', link: '/quick-start' },
          { text: 'API', link: '/api/memories' },
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
          { text: '快速上手', link: '/zh/quick-start' },
          { text: 'API', link: '/zh/api/memories' },
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
      pattern: `${GITHUB_REPO}/edit/main/repo_pages/:path`,
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the Apache-2.0 License.',
      copyright: 'Copyright 2026 afx-team',
    },
  },
})