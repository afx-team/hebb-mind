# SEO & AI-Search Optimization — Hebb Mind docs (2026-06-11)

Internal playbook for the SEO pass on the public VitePress site
(`repo_pages/` → https://afx-team.github.io/hebb-mind/). Covers what shipped,
what the maintainer must still do **by hand**, and ranked future work.

Grounded in source-verified research (VitePress 1.6.4 internals, llmstxt.org,
Princeton GEO study, schema.org rich-result status, RFC 9309, the 2025-2026 AI
crawler landscape) — see the research appendix at the bottom for citations.

---

## What shipped in this pass

### On-page (per-page `description` frontmatter)
- Unique, keyword-rich meta `description` on **all 78 content pages** (39 EN +
  39 zh), hand-tuned per page for Google snippets *and* AI answer-engine
  extraction. EN ≤ ~155 chars; zh in native phrasing (not machine-translated).
- Homepage (EN + zh) given a dedicated `<title>` (`titleTemplate: false`) plus a
  description.

### Centralized technical SEO (`repo_pages/.vitepress/config.mts`)
All derived from the page path in `transformPageData` — no per-page wiring:
- **Canonical** `<link rel="canonical">` on every page (absolute, base-correct).
- **Open Graph + Twitter** cards (`summary_large_image`), `og:locale` +
  `og:locale:alternate`, pointing at the new social card.
- **hreflang** `en` / `zh-CN` / `x-default` — reciprocal & self-inclusive on
  both the EN page and its zh mirror (Google's requirement for i18n clusters).
- **JSON-LD structured data**:
  - Home: `@graph` of `SoftwareSourceCode` + `SoftwareApplication` +
    `Organization` (`afx-team`) + `WebSite` (no dead `SearchAction` — the
    sitelinks searchbox was retired Nov 2024).
  - Docs: `TechArticle` + `BreadcrumbList` (breadcrumbs are one of the few items
    here that still render a *visible* rich result).
  - FAQ: `FAQPage` auto-extracted from the page's real `## Question` sections
    (12 Q&As, EN + zh) so the markup mirrors visible content.
- **`sitemap.xml`** via `sitemap.hostname` + a `transformItems` shim that
  injects the `/hebb-mind/` base (VitePress omits the base from sitemap URLs —
  the #1 sub-path footgun) and base-corrects the auto hreflang alternates.
- **`lastUpdated: true`** — unlocks `<lastmod>` in the sitemap (freshness
  signal). Requires full git history in CI → added `fetch-depth: 0` to
  `deploy-pages.yml`.

### AI-search / GEO assets (`repo_pages/public/`)
- **`llms.txt`** — spec-correct (llmstxt.org) curated index: H1 + summary
  blockquote + fact-dense intro (headline benchmark numbers) + sectioned link
  lists reusing the page descriptions, with an `## Optional` tail.
- **`robots.txt`** — allow-everything (search + AI retrieval + training), with a
  `Sitemap:` line and documented intent for ~30 named bots. (See the sub-path
  caveat below — this file is advisory at the sub-path.)
- **`.nojekyll`** — stops GitHub from running Jekyll over the build (Jekyll drops
  `_`-prefixed files and is a documented cause of GSC "Couldn't fetch sitemap").
- **`og-image.jpg`** — 1200×630 branded social card (88 KB), rendered from an
  HTML template; wired in as the default `og:image` / `twitter:image`.

Build verified: `npm run docs:build` green; 78 `<loc>` + 78 `<lastmod>` + 156
hreflang alternates in the sitemap; 155 JSON-LD blocks parse with 0 errors;
canonical + hreflang present on all 78 content pages.

---

## ⚠️ Manual steps the maintainer MUST do (not automatable in-repo)

1. **Submit the sitemap in Google Search Console.** This is *mandatory*, not
   optional. The site is a GitHub Pages **project** page at a sub-path, and per
   RFC 9309 the only authoritative `robots.txt` is at the **host root**
   (`afx-team.github.io/robots.txt`) — which this repo does not own. So the
   `Sitemap:` line in our sub-path `robots.txt` is **not auto-discovered**.
   - Add a **URL-prefix property** for `https://afx-team.github.io/hebb-mind/`
     (verify via the HTML-file method — drop Google's verification file into
     `repo_pages/public/` so it deploys at the sub-path root).
   - Search Console → **Sitemaps** → submit
     `https://afx-team.github.io/hebb-mind/sitemap.xml`.
   - Repeat for **Bing Webmaster Tools**.
2. **(If afx-team controls the org-root `afx-team.github.io` repo)** add
   `Sitemap: https://afx-team.github.io/hebb-mind/sitemap.xml` to that repo's
   **root** `robots.txt`, and confirm it does **not** `Disallow: /hebb-mind/`.
3. After deploy, spot-check with the [Rich Results Test](https://search.google.com/test/rich-results)
   (Breadcrumb + Article should show eligible) and validate the social card in a
   sharing debugger.

---

## Recommended next work (ranked)

1. **Custom domain (e.g. `hebb-mind.dev` / `docs.hebb-mind.dev`).** Highest
   structural lever. You then own the host root → authoritative root
   `robots.txt` + `sitemap.xml`, a full-host Search Console **Domain property**,
   and link-equity consolidation (today, backlinks dilute across the shared
   `github.io` host). Set `SITE`/`BASE` in `config.mts`, add a `CNAME`, and
   canonical-consolidate. Compounding, not overnight.
2. **`vitepress-plugin-llms`** (used by Vite/Vue/Vitest). Auto-generates
   `llms.txt`, `llms-full.txt`, **and a per-page `.md` for every page** — the
   per-page `.md` is the part AI engines actually consume today (our hand-authored
   `llms.txt` is the index only; honest reality: no major engine consumes
   `llms.txt` *itself* yet). Verify it respects `base: '/hebb-mind/'`; it would
   replace our manual `public/llms.txt`, so adopt one or the other.
3. **Core Web Vitals — hero media.** `home_video.mp4` is **7.7 MB** (injected via
   JS, so not the LCP element, but a real bandwidth cost). Re-encode to
   720/1080p ≤ ~2 MB, strip audio; ideally add a WebP poster. LCP is currently
   gated by the SSR'd hero text, so impact is moderate but worth it on mobile.
4. **Dead assets.** `repo_pages/public/architecture-en.jpg` and
   `architecture-zh.jpg` (**4.5 MB each, 9 MB total**) are **unreferenced** —
   nothing links them (the homepage `<img>` is commented out and points at a
   non-existent `.png`). They ship to `dist` as pure deploy bloat. Safe to delete
   *if* not linked from the README/external posts — left in place pending owner
   confirmation.
5. **GEO content polish** (Princeton GEO: +~30-40% AI-citation lift from these,
   keyword tricks *hurt*): lead each page with a 40-60-word answer-first TL;DR;
   phrase H2s as the questions developers actually ask; one concrete
   stat/version/default every ~150-200 words; cite primary sources; keep
   "Last updated" visible (now on).

---

## Research appendix (sources)

- VitePress 1.6.4 sitemap/`transformPageData`/`lastUpdated` internals — verified
  against `node_modules/vitepress` source (generateSitemap, getGitTimestamp).
- llms.txt spec — llmstxt.org; adoption reality — Mueller "no AI system uses
  llms.txt" + Originality.AI tracking study.
- GEO — Aggarwal et al., *Generative Engine Optimization*, arXiv 2311.09735 (KDD 2024).
- Rich-result status — Google: sitelinks searchbox retired 2024-11-21; FAQ rich
  results restricted 2023, fully removed 2026-05-07 (FAQPage now AI-comprehension
  only); BreadcrumbList + Article still render.
- Sub-path robots.txt — RFC 9309 (host-root scope); CWV thresholds — web.dev
  (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1).
- AI crawler UA landscape (2025-2026) — OpenAI/Anthropic/Perplexity crawler docs,
  Cloudflare crawler reports.
