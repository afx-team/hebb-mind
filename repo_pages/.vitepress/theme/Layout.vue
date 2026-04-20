<script setup lang="ts">
import DefaultTheme from 'vitepress/theme'
import CopyMarkdown from './CopyMarkdown.vue'
import { useData } from 'vitepress'

const { frontmatter } = useData()
</script>

<template>
  <DefaultTheme.Layout>
    <template #doc-before>
      <CopyMarkdown v-if="frontmatter.layout !== 'home'" />
    </template>
  </DefaultTheme.Layout>
</template>