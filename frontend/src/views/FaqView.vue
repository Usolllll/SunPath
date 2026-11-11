<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  ChevronDown,
  Info,
  Search,
  AlertCircle,
  ExternalLink,
} from "lucide-vue-next";
import { api } from "../api";
import type { FaqItem } from "../api/types";
import { safeSourceUrl } from "../utils/realdata";
const items = ref<FaqItem[]>([]);
const categories = ref<string[]>([]);
const total = ref(0);
const q = ref("");
const category = ref("");
const busy = ref(false);
const failed = ref(false);
let request = 0;
let timer: ReturnType<typeof setTimeout> | undefined;
async function load() {
  const seq = ++request;
  busy.value = true;
  failed.value = false;
  try {
    const { data } = await api.faq({
      ...(q.value.trim() ? { q: q.value.trim() } : {}),
      ...(category.value ? { category: category.value } : {}),
    });
    if (seq !== request) return;
    items.value = data.items;
    total.value = data.total;
    if (data.categories?.length) categories.value = data.categories;
  } catch {
    if (seq === request) failed.value = true;
  } finally {
    if (seq === request) busy.value = false;
  }
}
function selectCategory(next: string) {
  category.value = next;
  void load();
}
watch(q, () => {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => void load(), 260);
});
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">ANSWERS BEFORE YOU DECIDE</div>
      <h1>先把疑问问清楚，再做决定</h1>
      <p>
        常见问题来自公开政策与产品口径整理，回答中标注来源；涉及当年政策时以官方公告为准。
      </p>
    </div>
  </div>
  <section class="panel faq-panel">
    <div class="faq-search">
      <el-input
        v-model="q"
        clearable
        placeholder="搜索问题 / 关键词（如：体检、批次、位次）"
        aria-label="搜索常见问题"
        ><template #prefix><Search :size="16" /></template
      ></el-input>
      <span class="faq-total">共 {{ total }} 条</span>
    </div>
    <div v-if="categories.length" class="faq-categories">
      <button
        :class="['faq-chip', { active: category === '' }]"
        @click="selectCategory('')"
      >
        全部
      </button>
      <button
        v-for="item in categories"
        :key="item"
        :class="['faq-chip', { active: category === item }]"
        @click="selectCategory(item === category ? '' : item)"
      >
        {{ item }}
      </button>
    </div>
    <div v-loading="busy" class="faq-body">
      <div v-if="failed" class="empty-state">
        <p>常见问题加载失败</p>
        <el-button @click="load">重新加载</el-button>
      </div>
      <template v-else-if="items.length">
        <details v-for="item in items" :key="item.id" class="faq-item">
          <summary>
            <span class="tag subtle faq-category">{{ item.category }}</span>
            <strong>{{ item.question }}</strong>
            <ChevronDown :size="16" class="faq-chevron" />
          </summary>
          <div class="faq-answer">
            <p>{{ item.answer }}</p>
            <p v-if="item.source || item.source_url" class="faq-source">
              <Info :size="12" />来源：{{ item.source || "官方公开信息" }}
              <a
                v-if="safeSourceUrl(item.source_url)"
                :href="safeSourceUrl(item.source_url) || '#'"
                target="_blank"
                rel="noopener noreferrer"
                >查看原文 <ExternalLink :size="11"
              /></a>
            </p>
          </div>
        </details>
      </template>
      <el-empty
        v-else
        description="没有找到匹配的问题，试试更换关键词或分类"
      ></el-empty>
    </div>
    <div class="faq-disclaimer">
      <AlertCircle :size="14" />回答为产品口径整理，不构成报考或录取承诺；真实投档与招生计划请以省考试院、高校招生章程为准。
    </div>
  </section>
</template>

<style scoped>
.faq-panel {
  padding: 22px 24px 20px;
}
.faq-search {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 15px;
}
.faq-search .el-input {
  max-width: 480px;
}
.faq-total {
  font-size: 10px;
  color: #98a4b5;
}
.faq-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.faq-chip {
  font-size: 10px;
  color: #77869c;
  background: #f3f6fa;
  border: 1px solid #e9eef6;
  border-radius: 20px;
  padding: 5px 13px;
  transition:
    color 0.15s,
    background 0.15s;
}
.faq-chip:hover {
  color: #4f7fbe;
  background: #eef4fc;
}
.faq-chip.active {
  color: #fff;
  background: #4f7fbe;
  border-color: #4f7fbe;
}
.faq-body {
  min-height: 220px;
  padding-top: 8px;
}
.faq-item {
  border-bottom: 1px solid #eff2f7;
}
.faq-item summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 4px;
  cursor: pointer;
  list-style: none;
}
.faq-item summary::-webkit-details-marker {
  display: none;
}
.faq-item summary strong {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: #435a78;
  line-height: 1.7;
}
.faq-category {
  flex-shrink: 0;
  font-size: 9px;
}
.faq-chevron {
  color: #a6b2c2;
  flex-shrink: 0;
  transition: transform 0.2s;
}
.faq-item[open] .faq-chevron {
  transform: rotate(180deg);
}
.faq-answer {
  padding: 2px 4px 16px 4px;
  font-size: 11px;
  color: #72829a;
  line-height: 1.9;
}
.faq-source {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 10px;
  color: #9aa8ba;
}
.faq-source a {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #4f7fbe;
}
.faq-source a:hover {
  text-decoration: underline;
}
.faq-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  border-top: 1px solid var(--line);
  margin-top: 12px;
  padding-top: 14px;
  font-size: 10px;
  color: #9aa8ba;
  line-height: 1.8;
}
.faq-disclaimer > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
</style>
