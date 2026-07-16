import { defineConfig, type HeadConfig, type PageData } from 'vitepress'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const GITHUB_REPO = 'https://github.com/afx-team/hebb-mind'

/* ===========================================================================
 *  SEO — Google + AI-search optimization
 *
 *  Centralized here (not per-page) so every page gets canonical URLs, Open
 *  Graph / Twitter cards, en↔zh hreflang alternates, and JSON-LD structured
 *  data without touching 78 markdown files. Per-page `description` frontmatter
 *  supplies the snippet text; everything below is derived from the path.
 *
 *  Hosting note: this is a GitHub Pages *project* page at the `/hebb-mind/`
 *  sub-path. robots.txt at the sub-path is NOT authoritative (it must live at
 *  the host root afx-team.github.io/robots.txt) — submit the sitemap directly
 *  in Google Search Console. See reports/ for the full SEO playbook.
 * ========================================================================= */

const SITE = 'https://afx-team.github.io'
const BASE = '/hebb-mind/'
const SITE_BASE = `${SITE}${BASE}` // absolute root of the deployed docs
const OG_IMAGE = `${SITE_BASE}og-image.jpg` // 1200×630 social card in public/
const SRC_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/** relativePath ("a/b.md", "index.md", "zh/index.md") → absolute canonical URL.
 * Mirrors VitePress's own .md→URL transform: index.md→directory, else .md→.html. */
function pageUrl(relativePath: string): string {
  const path = relativePath
    .replace(/(^|\/)index\.md$/, '$1')
    .replace(/\.md$/, '.html')
  return `${SITE_BASE}${path}`
}

/** Map any relativePath to its EN + zh counterparts for reciprocal hreflang. */
function counterparts(relativePath: string): { en: string; zh: string } {
  const en = relativePath.replace(/^zh\//, '')
  const zh = en === 'index.md' ? 'zh/index.md' : `zh/${en}`
  return { en, zh }
}

const SECTION_LABELS: Record<string, { en: string; zh: string }> = {
  guide: { en: 'Guide', zh: '指南' },
  concepts: { en: 'Concepts', zh: '核心概念' },
  api: { en: 'API Reference', zh: 'API' },
  advanced: { en: 'Advanced', zh: '进阶' },
  benchmarks: { en: 'Benchmarks', zh: '基准测试' },
  locomo: { en: 'LoCoMo', zh: 'LoCoMo' },
  longmemeval: { en: 'LongMemEval', zh: 'LongMemEval' },
  membench: { en: 'MemBench', zh: 'MemBench' },
  convomem: { en: 'ConvoMem', zh: 'ConvoMem' },
  personamem: { en: 'PersonaMem', zh: 'PersonaMem' },
}

/** Build a BreadcrumbList from the path: Home › Section › … › <page title>. */
function breadcrumbList(relativePath: string, isZh: boolean, title: string): object {
  const home = isZh ? `${SITE_BASE}zh/` : SITE_BASE
  const items: { name: string; item: string }[] = [
    { name: isZh ? '首页' : 'Home', item: home },
  ]
  const localeStripped = relativePath.replace(/^zh\//, '')
  const segs = localeStripped.replace(/\.md$/, '').split('/').filter(Boolean)
  // Drop a trailing "index" so a section landing page isn't doubled.
  if (segs[segs.length - 1] === 'index') segs.pop()
  let acc = isZh ? 'zh/' : ''
  segs.forEach((seg, i) => {
    acc += `${seg}/`
    const isLeaf = i === segs.length - 1
    const label = SECTION_LABELS[seg]
      ? isZh
        ? SECTION_LABELS[seg].zh
        : SECTION_LABELS[seg].en
      : isLeaf
        ? title
        : seg
    items.push({ name: isLeaf ? title : label, item: `${SITE_BASE}${acc}` })
  })
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: it.item,
    })),
  }
}

/** Homepage entity graph: honest OSS types (SoftwareSourceCode + Application),
 * the afx-team Organization, and the WebSite node (no dead SearchAction). */
function homeGraph(isZh: boolean): object {
  const org = `${SITE_BASE}#org`
  const website = `${SITE_BASE}#website`
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'SoftwareSourceCode',
        '@id': `${SITE_BASE}#software`,
        name: 'Hebb Mind',
        alternateName: 'hebb-mind',
        description:
          'Neuroscience-inspired long-term memory framework for AI agents — write, consolidate, recall, and forget. Python package, CLI, FastAPI server, and MCP server.',
        url: SITE_BASE,
        codeRepository: GITHUB_REPO,
        programmingLanguage: 'Python',
        runtimePlatform: 'Python 3.10+',
        keywords: [
          'AI agents',
          'long-term memory',
          'LLM memory',
          'agent memory',
          'RAG',
          'vector search',
          'memory consolidation',
          'MCP server',
        ],
        license: 'https://opensource.org/licenses/MIT',
        applicationCategory: 'DeveloperApplication',
        operatingSystem: 'Linux, macOS, Windows',
        downloadUrl: 'https://pypi.org/project/hebb-mind/',
        author: { '@id': org },
        maintainer: { '@id': org },
        publisher: { '@id': org },
      },
      {
        '@type': 'SoftwareApplication',
        '@id': `${SITE_BASE}#app`,
        name: 'Hebb Mind',
        description:
          'Open-source memory framework that gives AI agents persistent, consolidating long-term memory.',
        url: SITE_BASE,
        applicationCategory: 'DeveloperApplication',
        applicationSubCategory: 'AI Agent Memory Framework',
        operatingSystem: 'Linux, macOS, Windows',
        softwareRequirements: 'Python 3.10+',
        downloadUrl: 'https://pypi.org/project/hebb-mind/',
        license: 'https://opensource.org/licenses/MIT',
        isAccessibleForFree: true,
        sameAs: ['https://github.com/afx-team/hebb-mind', 'https://pypi.org/project/hebb-mind/'],
        author: { '@id': org },
        publisher: { '@id': org },
      },
      {
        '@type': 'Organization',
        '@id': org,
        name: 'afx-team',
        url: 'https://github.com/afx-team',
        logo: `${SITE_BASE}logo.svg`,
        sameAs: [
          'https://github.com/afx-team',
          'https://github.com/afx-team/hebb-mind',
          'https://pypi.org/project/hebb-mind/',
        ],
      },
      {
        '@type': 'WebSite',
        '@id': website,
        name: 'Hebb Mind',
        url: SITE_BASE,
        description:
          'Documentation for Hebb Mind, the neuroscience-inspired memory framework for AI agents.',
        publisher: { '@id': org },
        inLanguage: isZh ? 'zh-CN' : 'en',
      },
    ],
  }
}

/** TechArticle node for a documentation page. */
function techArticle(
  url: string,
  title: string,
  description: string,
  isZh: boolean,
  section: string,
  lastUpdated?: number,
): object {
  return {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    headline: title,
    description,
    url,
    inLanguage: isZh ? 'zh-CN' : 'en',
    articleSection: section,
    isPartOf: { '@type': 'WebSite', '@id': `${SITE_BASE}#website`, name: 'Hebb Mind', url: SITE_BASE },
    author: { '@id': `${SITE_BASE}#org` },
    publisher: { '@id': `${SITE_BASE}#org` },
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    ...(lastUpdated ? { dateModified: new Date(lastUpdated).toISOString() } : {}),
  }
}

/** Strip markdown to plain text for FAQ answer extraction. */
function mdToText(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, ' ') // fenced code
    .replace(/`([^`]+)`/g, '$1') // inline code
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ') // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // links → text
    .replace(/^[>\s]*:::.*$/gm, ' ') // vitepress containers
    .replace(/[*_#>]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Parse a FAQ source file's "## Question" sections into Q&A pairs.
 * Returns text that mirrors the visible page (Google + AI-search requirement). */
function extractFaq(relativePath: string): { q: string; a: string }[] {
  try {
    const raw = readFileSync(resolve(SRC_DIR, relativePath), 'utf-8')
    const body = raw.replace(/^---[\s\S]*?\n---\n/, '') // drop frontmatter
    const out: { q: string; a: string }[] = []
    const parts = body.split(/\n(?=##\s)/)
    for (const part of parts) {
      const m = part.match(/^##\s+(.+?)\s*\n([\s\S]*)$/)
      if (!m) continue
      const q = mdToText(m[1])
      // answer = up to the next ### subheading; cap length for sane snippets
      const a = mdToText(m[2].split(/\n###\s/)[0]).slice(0, 320)
      // Accept both ASCII '?' and the full-width '？' used in Chinese headings.
      if (q && a && /[?？]$/.test(q)) out.push({ q, a })
    }
    return out.slice(0, 12)
  } catch {
    return []
  }
}

function faqPage(url: string, isZh: boolean, qas: { q: string; a: string }[]): object {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    url,
    inLanguage: isZh ? 'zh-CN' : 'en',
    isPartOf: { '@id': `${SITE_BASE}#website` },
    mainEntity: qas.map((x) => ({
      '@type': 'Question',
      name: x.q,
      acceptedAnswer: { '@type': 'Answer', text: x.a },
    })),
  }
}

/** Build all per-page SEO <head> tags from PageData. */
function seoHead(pageData: PageData): HeadConfig[] {
  const fm = pageData.frontmatter
  const rel = pageData.relativePath
  const isZh = rel.startsWith('zh/')
  const url = pageUrl(rel)
  const title = (fm.title ?? pageData.title ?? 'Hebb Mind') as string
  const description = (fm.description ?? pageData.description ?? '') as string
  const { en, zh } = counterparts(rel)
  const isHome = rel === 'index.md' || rel === 'zh/index.md'
  const isFaq = rel === 'faq.md' || rel === 'zh/faq.md'
  const section = SECTION_LABELS[rel.replace(/^zh\//, '').split('/')[0]]
    ? (isZh ? SECTION_LABELS[rel.replace(/^zh\//, '').split('/')[0]].zh : SECTION_LABELS[rel.replace(/^zh\//, '').split('/')[0]].en)
    : 'Documentation'

  const head: HeadConfig[] = [
    ['link', { rel: 'canonical', href: url }],
    ['link', { rel: 'alternate', hreflang: 'en', href: pageUrl(en) }],
    ['link', { rel: 'alternate', hreflang: 'zh-CN', href: pageUrl(zh) }],
    ['link', { rel: 'alternate', hreflang: 'x-default', href: pageUrl(en) }],
    ['meta', { property: 'og:title', content: title }],
    ['meta', { property: 'og:description', content: description }],
    ['meta', { property: 'og:type', content: isHome ? 'website' : 'article' }],
    ['meta', { property: 'og:url', content: url }],
    ['meta', { property: 'og:image', content: OG_IMAGE }],
    ['meta', { property: 'og:site_name', content: 'Hebb Mind' }],
    ['meta', { property: 'og:locale', content: isZh ? 'zh_CN' : 'en_US' }],
    ['meta', { property: 'og:locale:alternate', content: isZh ? 'en_US' : 'zh_CN' }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: title }],
    ['meta', { name: 'twitter:description', content: description }],
    ['meta', { name: 'twitter:image', content: OG_IMAGE }],
  ]

  // JSON-LD: software graph on home, FAQPage on FAQ, TechArticle elsewhere.
  const ld: object[] = []
  if (isHome) {
    ld.push(homeGraph(isZh))
  } else {
    ld.push(techArticle(url, title, description, isZh, section, pageData.lastUpdated))
    ld.push(breadcrumbList(rel, isZh, title))
    if (isFaq) {
      const qas = extractFaq(rel)
      if (qas.length) ld.push(faqPage(url, isZh, qas))
    }
  }
  for (const obj of ld) {
    head.push(['script', { type: 'application/ld+json' }, JSON.stringify(obj)])
  }
  return head
}

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
        { text: prefix ? 'Agent 同步' : 'Agent Sync', link: `${prefix}/guide/agent-sync` },
        { text: prefix ? '导入 Agent 记忆' : 'Import Agent Memory', link: `${prefix}/guide/import` },
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
        // folder. The Chinese mirror has the LoCoMo tree translated;
        // the remaining datasets still fall back to the legacy page.
        prefix
          ? {
              text: '基准测试',
              link: `${prefix}/benchmarks/`,
              collapsed: true,
              items: [
                {
                  text: 'LoCoMo',
                  link: `${prefix}/benchmarks/locomo/`,
                  collapsed: true,
                  items: [
                    { text: 'vs MemPalace', link: `${prefix}/benchmarks/locomo/vs-mempalace` },
                    { text: 'vs mem0', link: `${prefix}/benchmarks/locomo/vs-mem0` },
                    { text: 'vs Letta', link: `${prefix}/benchmarks/locomo/vs-letta` },
                    { text: 'vs Zep', link: `${prefix}/benchmarks/locomo/vs-zep` },
                  ],
                },
                {
                  text: 'LongMemEval',
                  link: `${prefix}/benchmarks/longmemeval/`,
                  collapsed: true,
                  items: [
                    { text: 'vs MemPalace', link: `${prefix}/benchmarks/longmemeval/vs-mempalace` },
                    { text: 'vs mem0', link: `${prefix}/benchmarks/longmemeval/vs-mem0` },
                    { text: 'vs Zep / Graphiti', link: `${prefix}/benchmarks/longmemeval/vs-zep` },
                  ],
                },
                { text: 'MemBench', link: `${prefix}/benchmarks/membench/` },
              ],
            }
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
                    { text: 'vs mem0', link: '/benchmarks/longmemeval/vs-mem0' },
                    { text: 'vs Zep / Graphiti', link: '/benchmarks/longmemeval/vs-zep' },
                  ],
                },
                { text: 'MemBench', link: '/benchmarks/membench/' },
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

  /* Compute pageData.lastUpdated AND unlock <lastmod> in the sitemap.
   * Requires full git history in CI (actions/checkout fetch-depth: 0). */
  lastUpdated: true,

  /* sitemap.xml — the `sitemap` lib prepends `hostname` only and does NOT add
   * the `/hebb-mind/` base, so we inject it (and the hreflang alternates' base)
   * via transformItems. Submit the result in Google Search Console. */
  sitemap: {
    hostname: SITE,
    transformItems: (items) =>
      items.map((item) => ({
        ...item,
        url: `hebb-mind/${item.url.replace(/^\//, '')}`,
        links: item.links?.map((l) => ({
          ...l,
          url: `hebb-mind/${String(l.url).replace(/^\//, '')}`,
        })),
      })),
  },

  /* Per-page canonical, Open Graph, Twitter, hreflang & JSON-LD (see seoHead). */
  transformPageData(pageData) {
    const fm = pageData.frontmatter
    if ((fm.head as { __seo?: boolean })?.__seo) return // idempotency under HMR
    const arr = (fm.head ??= []) as HeadConfig[]
    arr.push(...seoHead(pageData))
    Object.defineProperty(arr, '__seo', { value: true, enumerable: false })
  },

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/hebb-mind/logo.svg' }],
    // Static SEO tags shared by every page (per-page og/twitter/canonical/JSON-LD
    // are injected in transformPageData below).
    ['meta', { name: 'author', content: 'afx-team' }],
    ['meta', { name: 'theme-color', content: '#0d1117' }],
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],
    ['meta', { property: 'og:image:type', content: 'image/jpeg' }],
    // Cloudflare Web Analytics: privacy-first, no cookies. The beacon tracks
    // SPA navigations on its own via the History API, so no theme hook is
    // needed. The token is public (shipped in every page), not a secret.
    [
      'script',
      {
        defer: '',
        src: 'https://static.cloudflareinsights.com/beacon.min.js',
        'data-cf-beacon': '{"token": "d435c0d92eb64c608a59987e2e5512bb"}',
      },
    ],
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
          { text: '基准测试', link: '/zh/benchmarks/' },
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
