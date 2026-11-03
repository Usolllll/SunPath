<script setup lang="ts">
import { computed } from "vue";
import { renderMarkdown } from "../utils/markdown";

const props = defineProps<{ content: string }>();
const rendered = computed(() => renderMarkdown(props.content));
</script>

<template>
  <!-- Only parser-generated markup is rendered; raw HTML is disabled. -->
  <div class="markdown-content" v-html="rendered"></div>
</template>

<style scoped>
.markdown-content {
  overflow-wrap: anywhere;
}
.markdown-content :deep(> :first-child) {
  margin-top: 0;
}
.markdown-content :deep(> :last-child) {
  margin-bottom: 0;
}
.markdown-content :deep(p) {
  margin: 0 0 0.85em;
}
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  font-size: 1.08em;
  font-weight: 600;
  color: #304d73;
  margin: 1.1em 0 0.55em;
  line-height: 1.6;
}
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 1.7em;
  margin: 0.6em 0 1em;
}
.markdown-content :deep(ul) {
  list-style: disc;
}
.markdown-content :deep(ol) {
  list-style: decimal;
}
.markdown-content :deep(li) {
  margin: 0.3em 0;
}
.markdown-content :deep(li > p) {
  margin-bottom: 0.35em;
}
.markdown-content :deep(strong) {
  font-weight: 600;
  color: #365579;
}
.markdown-content :deep(a) {
  color: #3374cb;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.markdown-content :deep(blockquote) {
  margin: 0.8em 0;
  padding: 0.2em 1em;
  border-left: 3px solid #bfd0e7;
  color: #72839a;
}
.markdown-content :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
  padding: 12px;
  margin: 0.8em 0;
  background: #eaf0f7;
  border-radius: 6px;
  line-height: 1.65;
}
.markdown-content :deep(code) {
  font-family: Consolas, monospace;
  font-size: 0.92em;
  background: #eaf0f7;
  border-radius: 3px;
  padding: 0.12em 0.3em;
}
.markdown-content :deep(pre code) {
  padding: 0;
  background: none;
}
.markdown-content :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 0.8em 0;
}
.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #dce4ef;
  padding: 7px 11px;
  min-width: 80px;
}
.markdown-content :deep(th) {
  background: #edf2f9;
  font-weight: 600;
}
.markdown-content :deep(hr) {
  border: 0;
  border-top: 1px solid #dce4ef;
  margin: 1em 0;
}
</style>
