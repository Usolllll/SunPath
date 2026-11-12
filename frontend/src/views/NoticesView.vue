<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  ArrowUpRight,
  Info,
  Newspaper,
  Search,
} from "lucide-vue-next";
import { api } from "../api";
import type { NoticeItem } from "../api/types";
import { NOTICE_CATEGORY_FALLBACK } from "../utils/process";
import { safeSourceUrl } from "../utils/realdata";
const items = ref<NoticeItem[]>([]);
const categories = ref<string[]>([...NOTICE_CATEGORY_FALLBACK]);
const total = ref(0);
const q = ref("");
const category = ref("");
const busy = ref(false);
const failed = ref(false);
const drawer = ref(false);
const detail = ref<NoticeItem | null>(null);
const detailBusy = ref(false);
let request = 0;
let timer: ReturnType<typeof setTimeout> | undefined;

async function load() {
  const seq = ++request;
  busy.value = true;
  failed.value = false;
  try {
    const { data } = await api.notices({
      ...(category.value ? { category: category.value } : {}),
      ...(q.value.trim() ? { q: q.value.trim() } : {}),
      limit: 50,
    });
    if (seq !== request) return;
    items.value = data.items ?? [];
    total.value = data.total ?? 0;
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
async function open(item: NoticeItem) {
  detail.value = item;
  drawer.value = true;
  detailBusy.value = true;
  try {
    detail.value = (await api.notice(item.id)).data;
  } catch {
    /* 列表数据已足够展示摘要，详情接口失败时保留列表内容 */
  } finally {
    detailBusy.value = false;
  }
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
      <div class="eyebrow">POLICY, PLAINLY EXPLAINED</div>
      <h1>政策变化，第一时间看懂</h1>
      <p>
        分类浏览招生政策、志愿填报、数据公告与院校宣讲资讯；每条都标注来源，具体以官方原文为准。
      </p>
    </div>
  </div>
  <section class="panel notices-panel">
    <div class="notices-toolbar">
      <el-input
        v-model="q"
        clearable
        placeholder="搜索标题 / 关键词（如：批次、专项计划、征集）"
        aria-label="搜索政策资讯"
        ><template #prefix><Search :size="16" /></template
      ></el-input>
      <span class="notices-total">共 {{ total }} 条</span>
    </div>
    <div class="notices-categories">
      <button
        :class="['notice-chip', { active: category === '' }]"
        @click="selectCategory('')"
      >
        全部
      </button>
      <button
        v-for="item in categories"
        :key="item"
        :class="['notice-chip', { active: category === item }]"
        @click="selectCategory(item === category ? '' : item)"
      >
        {{ item }}
      </button>
    </div>
    <div v-loading="busy" class="notices-body">
      <div v-if="failed" class="empty-state">
        <p>政策资讯加载失败</p>
        <el-button @click="load">重新加载</el-button>
      </div>
      <div v-else-if="items.length" class="notices-grid">
        <article
          v-for="item in items"
          :key="item.id"
          class="notice-card"
          role="button"
          tabindex="0"
          @click="open(item)"
          @keydown.enter="open(item)"
        >
          <div class="notice-card-head">
            <span class="tag">{{ item.category }}</span>
            <span class="notice-date">{{ item.publish_date }}</span>
          </div>
          <h3>{{ item.title }}</h3>
          <p class="notice-summary">{{ item.summary }}</p>
          <div class="notice-foot">
            <span v-if="item.source" class="notice-source">{{
              item.source
            }}</span>
            <span
              v-for="tag in item.tags"
              :key="tag"
              class="tag subtle notice-tag"
              >{{ tag }}</span
            >
            <span class="notice-more">查看详情 <ArrowUpRight :size="12" /></span>
          </div>
        </article>
      </div>
      <el-empty
        v-else
        description="没有找到匹配的资讯，试试更换关键词或分类"
      ></el-empty>
    </div>
    <div class="notices-disclaimer">
      <Info :size="14" />资讯为公开信息摘要，不构成报考建议；政策口径以省考试院与高校当年公告为准。
    </div>
  </section>

  <el-drawer
    v-model="drawer"
    title="政策资讯详情"
    size="min(560px, 100%)"
  >
    <div v-if="detail" v-loading="detailBusy" class="notice-detail">
      <div class="notice-detail-meta">
        <span class="tag">{{ detail.category }}</span>
        <span>{{ detail.publish_date }}</span>
      </div>
      <h2>{{ detail.title }}</h2>
      <p class="notice-detail-summary">{{ detail.summary }}</p>
      <div v-if="detail.tags.length" class="notice-detail-tags">
        <span v-for="tag in detail.tags" :key="tag" class="tag subtle">{{
          tag
        }}</span>
      </div>
      <p class="notice-detail-source">
        <Newspaper :size="13" />来源：{{ detail.source || "未标注" }}
        <a
          v-if="safeSourceUrl(detail.source_url)"
          :href="safeSourceUrl(detail.source_url) || '#'"
          target="_blank"
          rel="noopener noreferrer"
          >查看原文 <ArrowUpRight :size="12"
        /></a>
      </p>
      <p class="notice-detail-note">
        资讯内容为公开信息摘要，具体条款与时间以官方原文和当年政策为准。
      </p>
    </div>
  </el-drawer>
</template>

<style scoped>
.notices-panel {
  padding: 21px 23px 18px;
}
.notices-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 14px;
}
.notices-toolbar .el-input {
  max-width: 460px;
}
.notices-total {
  font-size: 10px;
  color: #98a4b5;
}
.notices-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.notice-chip {
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
.notice-chip:hover {
  color: #4f7fbe;
  background: #eef4fc;
}
.notice-chip.active {
  color: #fff;
  background: #4f7fbe;
  border-color: #4f7fbe;
}
.notices-body {
  min-height: 220px;
  padding-top: 16px;
}
.notices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}
.notice-card {
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  padding: 15px 17px 13px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}
.notice-card:hover,
.notice-card:focus-visible {
  border-color: #d7e3f3;
  box-shadow: 0 3px 12px #2037560d;
}
.notice-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.notice-card h3 {
  font-size: 13px;
  font-weight: 500;
  color: #3f5674;
  line-height: 1.65;
}
.notice-summary {
  font-size: 10px;
  color: #8b9bb1;
  line-height: 1.85;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.notice-foot {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 3px;
}
.notice-source {
  font-size: 9px;
  color: #9aa8ba;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notice-tag {
  font-size: 8px;
}
.notice-more {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 9px;
  color: #4f7fbe;
  margin-left: auto;
  white-space: nowrap;
}
.notice-date {
  font-size: 10px;
  color: #a2afc0;
}
.notices-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  border-top: 1px solid var(--line);
  margin-top: 16px;
  padding-top: 13px;
  font-size: 10px;
  color: #9aa8ba;
  line-height: 1.8;
}
.notices-disclaimer > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.notice-detail {
  font-size: 12px;
  color: #6f819b;
}
.notice-detail-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 10px;
  color: #9aa8ba;
}
.notice-detail h2 {
  font-size: 20px;
  line-height: 1.55;
  color: #2b405f;
  margin: 12px 0;
}
.notice-detail-summary {
  font-size: 12px;
  line-height: 2;
  color: #6f819b;
}
.notice-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}
.notice-detail-source {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: 18px;
  padding-top: 13px;
  border-top: 1px solid var(--line);
  font-size: 10px;
  color: #8b9bb1;
}
.notice-detail-source a {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #4f7fbe;
  margin-left: 4px;
}
.notice-detail-source a:hover {
  text-decoration: underline;
}
.notice-detail-note {
  font-size: 10px;
  color: #a2afc0;
  line-height: 1.8;
  margin-top: 14px;
}
</style>
