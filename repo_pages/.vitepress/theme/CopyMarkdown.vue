<script setup lang="ts">
import { ref, computed } from 'vue'
import { useData } from 'vitepress'

const { page, lang } = useData()

const REPO_RAW = 'https://raw.githubusercontent.com/afx-team/hippocampus/main/docs/'

const state = ref<'idle' | 'loading' | 'copied' | 'error'>('idle')

const label = computed(() => {
  const zh = lang.value === 'zh-CN'
  switch (state.value) {
    case 'loading': return zh ? '获取中...' : 'Loading...'
    case 'copied':  return zh ? '已复制!' : 'Copied!'
    case 'error':   return zh ? '复制失败' : 'Failed'
    default:        return zh ? '复制为 Markdown (LLM)' : 'Copy as Markdown (LLM)'
  }
})

async function copy() {
  if (state.value === 'loading' || state.value === 'copied') return
  state.value = 'loading'

  try {
    // Fetch raw markdown from GitHub
    const url = REPO_RAW + page.value.relativePath
    const res = await fetch(url)
    let text: string

    if (res.ok) {
      text = await res.text()
      // Strip VitePress frontmatter
      text = text.replace(/^---[\s\S]*?---\n*/, '')
    } else {
      // Fallback: extract text from the rendered page
      const article = document.querySelector('.vp-doc')
      text = article?.innerText ?? document.body.innerText
    }

    await navigator.clipboard.writeText(text.trim())
    state.value = 'copied'
  } catch {
    // Final fallback
    try {
      const article = document.querySelector('.vp-doc')
      const text = article?.innerText ?? ''
      await navigator.clipboard.writeText(text.trim())
      state.value = 'copied'
    } catch {
      state.value = 'error'
    }
  }

  setTimeout(() => { state.value = 'idle' }, 2000)
}
</script>

<template>
  <button
    class="copy-md-btn"
    :class="state"
    :disabled="state === 'loading'"
    @click="copy"
    :title="label"
  >
    <svg v-if="state === 'idle'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
    <svg v-else-if="state === 'copied'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
    <svg v-else-if="state === 'loading'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
    <span>{{ label }}</span>
  </button>
</template>

<style scoped>
.copy-md-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 6px;
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-2);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 24px;
}
.copy-md-btn:hover {
  border-color: var(--vp-c-brand-1);
  color: var(--vp-c-brand-1);
}
.copy-md-btn.copied {
  border-color: var(--vp-c-green-1);
  color: var(--vp-c-green-1);
}
.copy-md-btn.error {
  border-color: var(--vp-c-danger-1);
  color: var(--vp-c-danger-1);
}
.copy-md-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1s linear infinite; }
</style>
