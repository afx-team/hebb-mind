import { defineConfig } from 'vitepress'

const GITHUB_REPO = 'https://github.com/afx-team/hebb-mind'

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
        { text: prefix ? '切换 Embedding 模型' : 'Switch Embedding Model', link: `${prefix}/guide/switch-embedding-model` },
        { text: 'Claude Code', link: `${prefix}/guide/claude-code` },
        { text: 'Codex', link: `${prefix}/guide/codex` },
        { text: prefix ? 'MCP 集成' : 'MCP Integration', link: `${prefix}/guide/mcp-integration` },
        { text: prefix ? 'Web 控制台' : 'Web Console', link: `${prefix}/guide/web-console` },
        { text: prefix ? '从其他系统迁移' : 'Migration from mem0 / Letta / Zep', link: `${prefix}/guide/migration` },
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
      ],
    },
    {
      text: prefix ? '资源' : 'Resources',
      items: [
        { text: prefix ? '故障排查' : 'Troubleshooting', link: `${prefix}/troubleshooting` },
        { text: prefix ? '常见问题' : 'FAQ', link: `${prefix}/faq` },
        // The English benchmarks page is split into a per-dataset
        // folder; the Chinese mirror is still the single legacy page.
        // Surface the deep tree only on the English side.
        prefix
          ? { text: '基准测试', link: `${prefix}/benchmarks` }
          : {
              text: 'Benchmarks',
              link: '/benchmarks/',
              collapsed: true,
              items: [
                {
                  text: 'LoCoMo',
                  link: '/benchmarks/locomo/',
                  collapsed: true,
                  items: [
                    { text: 'vs MemPalace', link: '/benchmarks/locomo/vs-mempalace' },
                    { text: 'vs mem0', link: '/benchmarks/locomo/vs-mem0' },
                    { text: 'vs Letta', link: '/benchmarks/locomo/vs-letta' },
                    { text: 'vs Zep', link: '/benchmarks/locomo/vs-zep' },
                  ],
                },
                {
                  text: 'LongMemEval',
                  link: '/benchmarks/longmemeval/',
                  collapsed: true,
                  items: [
                    { text: 'vs MemPalace', link: '/benchmarks/longmemeval/vs-mempalace' },
                    { text: 'vs Zep / Graphiti', link: '/benchmarks/longmemeval/vs-zep' },
                  ],
                },
                { text: 'PersonaMem', link: '/benchmarks/personamem/' },
              ],
            },
      ],
    },
  ]
}

export default defineConfig({
  title: 'Hebb Mind',
  description: 'Neuroscience-inspired memory framework for AI agents',

  /* GitHub Pages sub-path */
  base: '/hebb-mind/',

  /* dark mode default */
  appearance: 'dark',

  /* localhost links are runtime references, not doc links */
  ignoreDeadLinks: [
    /localhost/,
  ],

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/hebb-mind/logo.svg' }],
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
          { text: 'Benchmarks', link: '/benchmarks/' },
          { text: 'FAQ', link: '/faq' },
        ],
        sidebar: guideSidebar(),
      },
    },
    zh: {
      label: '中文',
      lang: 'zh-CN',
      title: 'Hebb Mind',
      description: '受神经科学启发的 AI Agent 记忆框架',
      themeConfig: {
        nav: [
          { text: '快速上手', link: '/zh/quick-start' },
          { text: 'API', link: '/zh/api/memories' },
          { text: '基准测试', link: '/zh/benchmarks' },
          { text: '常见问题', link: '/zh/faq' },
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
    siteTitle: 'Hebb Mind',

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
      message: 'Released under the MIT License.',
      copyright: 'Copyright 2026 afx-team',
    },
  },
})
