<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArrowUpRight,
  Database,
  Info,
  RefreshCw,
  ShieldCheck,
  Activity,
  Heart,
  AlertCircle,
  CheckCircle2,
} from "lucide-vue-next";
import { useRouter } from "vue-router";
import { api } from "../api";
import type { DataQuality, PatrolItem, PopularityItem } from "../api/types";
import { date, number } from "../utils/format";
import { coverageText, safeSourceUrl, yearSpan } from "../utils/realdata";
import { patrolCheckedText } from "../utils/rtm";
const router = useRouter();
const quality = ref<DataQuality | null>(null);
const popularity = ref<PopularityItem[]>([]);
const popularityFailed = ref(false);
const busy = ref(false);
const failed = ref(false);
const realCoverage = computed(() => coverageText(quality.value?.real ?? null));
const simulatedCards = computed(() => {
  const simulated = quality.value?.simulated;
  if (!simulated) return [];
  return [
    { key: "universities", label: "院校", value: simulated.universities },
    { key: "groups", label: "专业组", value: simulated.groups },
    { key: "admissions", label: "历年录取记录", value: simulated.admissions },
    { key: "enrollments", label: "招生计划", value: simulated.enrollments },
    { key: "major_cards", label: "专业介绍卡", value: simulated.major_cards },
  ];
});
const counts = computed(() =>
  quality.value
    ? [
        { label: "收藏", value: quality.value.counts.favorites },
        { label: "方案", value: quality.value.counts.plans },
        { label: "FAQ", value: quality.value.counts.faq },
        { label: "审计日志", value: quality.value.counts.audit_logs },
      ]
    : [],
);
const patrolItems = computed(() => quality.value?.patrol?.items ?? []);
function sourceOf(url: string | null | undefined) {
  return safeSourceUrl(url);
}
function dateText(value: string | null | undefined) {
  return value ? date(value) : "未标注";
}
async function load() {
  busy.value = true;
  failed.value = false;
  popularityFailed.value = false;
  try {
    quality.value = (await api.dataQuality()).data;
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
  if (!quality.value) return;
  try {
    const payload = (await api.popularity(10)).data;
    popularity.value = Array.isArray(payload) ? payload : payload?.items ?? [];
  } catch {
    popularity.value = [];
    popularityFailed.value = true;
  }
}
function patrolState(item: PatrolItem) {
  if (item.ok === false) return "异常";
  return "正常";
}
function patrolHttpStatus(item: PatrolItem) {
  return item.status == null ? "" : `HTTP ${item.status}`;
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">KNOW WHERE THE DATA COMES FROM</div>
      <h1>数据从哪来，更新到哪一步</h1>
      <p>
        真实官方投档数据与模拟样本库分开存放；这里展示覆盖、版本台账、源巡检与真实用户行为计数。
      </p>
    </div>
    <div class="heading-actions">
      <el-button :loading="busy" @click="load"
        ><RefreshCw :size="15" />刷新</el-button
      >
    </div>
  </div>
  <div v-loading="busy" class="quality-area">
    <div v-if="failed" class="empty-state">
      <p>数据质量信息加载失败</p>
      <el-button @click="load">重新加载</el-button>
    </div>
    <div v-else-if="quality" class="quality-grid">
      <section class="panel quality-card coverage-card">
        <div class="quality-card-head">
          <h3><ShieldCheck :size="16" />官方真实投档数据覆盖</h3>
          <span class="tag warm">真实数据 · 官方来源</span>
        </div>
        <p class="coverage-title">{{ realCoverage }}</p>
        <div class="coverage-provinces">
          <div
            v-for="item in quality.real.provinces"
            :key="item.province"
            class="coverage-province"
          >
            <strong>{{ item.province }}</strong>
            <span
              >{{ number(item.rows) }} 条 · {{ number(item.schools) }} 所</span
            >
            <span class="muted">{{ yearSpan(item.years) }}</span>
            <span class="muted">数据发布 {{ item.published_at || "未标注" }}</span>
          </div>
        </div>
        <div class="coverage-foot">
          <button class="text-button" @click="router.push('/data?tab=realdata')">
            去招生数据中心核对 <ArrowUpRight :size="13" />
          </button>
          <span class="muted"
            >共 {{ number(quality.real.total_rows) }} 条真实投档记录</span
          >
        </div>
      </section>
      <section class="panel quality-card">
        <div class="quality-card-head">
          <h3><Database :size="16" />模拟样本库</h3>
          <span class="tag subtle">模拟 · 仅供演示</span>
        </div>
        <div class="simulated-grid">
          <div v-for="card in simulatedCards" :key="card.key">
            <strong>{{ number(card.value) }}</strong><span>{{ card.label }}</span>
          </div>
        </div>
        <p class="quality-note">
          模拟数据只用于演示匹配与冲稳保分级，不代表真实招生或录取结果。
        </p>
      </section>
      <section class="panel quality-card quality-wide">
        <div class="quality-card-head">
          <h3><Activity :size="16" />数据版本台账</h3>
          <span class="tag subtle">按导入批次留痕</span>
        </div>
        <el-table
          v-if="quality.versions.length"
          :data="quality.versions"
          size="small"
          class="version-table"
        >
          <el-table-column label="数据集" min-width="90"
            ><template #default="{ row }">{{ row.dataset }}</template></el-table-column
          >
          <el-table-column label="省份 / 年份" min-width="110"
            ><template #default="{ row }">{{
              [row.province, row.exam_year].filter(Boolean).join(" · ") ||
              "—"
            }}</template></el-table-column
          >
          <el-table-column label="行数" width="100"
            ><template #default="{ row }">{{
              number(row.row_count)
            }}</template></el-table-column
          >
          <el-table-column label="发布于" width="110"
            ><template #default="{ row }">{{
              row.published_at || "未标注"
            }}</template></el-table-column
          >
          <el-table-column label="状态" width="90"
            ><template #default="{ row }"
              ><span class="tag" :class="{ warm: row.is_current }">{{
                row.doc_status || (row.is_current ? "当前版本" : "历史版本")
              }}</span></template
            ></el-table-column
          >
          <el-table-column label="公告" width="108"
            ><template #default="{ row }"
              ><a
                v-if="sourceOf(row.source_url)"
                :href="sourceOf(row.source_url) || '#'"
                target="_blank"
                rel="noopener noreferrer"
                class="version-link"
                >查看公告 ↗</a
              ><span v-else class="muted">未收录</span></template
            ></el-table-column
          >
        </el-table>
        <p v-else class="quality-note">暂无数据版本记录。</p>
      </section>
      <section class="panel quality-card">
        <div class="quality-card-head">
          <h3><Activity :size="16" />数据源巡检</h3>
          <span v-if="quality.patrol" class="tag subtle"
            >最近巡检 {{ patrolCheckedText(quality.patrol.last_checked_at) }}</span
          >
        </div>
        <template v-if="quality.patrol && patrolItems.length">
          <div
            v-for="(item, index) in patrolItems"
            :key="`${item.dataset}-${index}`"
            class="patrol-row"
          >
            <CheckCircle2
              v-if="item.ok !== false"
              :size="14"
              class="patrol-ok"
            />
            <AlertCircle v-else :size="14" class="patrol-bad" />
            <span class="patrol-dataset">{{ item.dataset }}</span>
            <span class="tag" :class="{ warm: item.ok === false }">{{
              patrolState(item)
            }}</span>
            <span class="muted patrol-meta">
              {{ patrolHttpStatus(item) }}
              {{ item.changed ? "内容有变化" : "内容无变化" }} ·
              {{ item.checked_at || "时间未标注" }}
            </span>
          </div>
        </template>
        <p v-else class="quality-note">暂无巡检记录。</p>
        <p class="quality-note">
          巡检只比对来源文件哈希与发布时间，用于发现更新；不改变任何已入库数据。
        </p>
      </section>
      <section class="panel quality-card">
        <div class="quality-card-head">
          <h3><Heart :size="16" />收藏热度 Top</h3>
          <span class="tag subtle">真实用户行为</span>
        </div>
        <ol v-if="popularity.length" class="popularity-list">
          <li
            v-for="(item, index) in popularity"
            :key="item.university_id"
            class="popularity-item"
          >
            <span class="popularity-rank" :class="{ top: index < 3 }">{{
              index + 1
            }}</span>
            <div class="popularity-school">
              <strong>{{ item.name }}</strong>
              <p>
                {{ item.city }} · {{ item.level }}
                <span v-if="item.level_tier != null"
                  >· 层次 {{ item.level_tier }}</span
                >
              </p>
            </div>
            <span class="popularity-count"
              >{{ item.favorites }} <small>人收藏</small></span
            >
          </li>
        </ol>
        <p v-else class="quality-note">
          {{
            popularityFailed
              ? "收藏热度暂时无法获取。"
              : "暂无收藏热度数据（真实用户行为，非模拟）。"
          }}
        </p>
      </section>
      <section class="panel quality-card">
        <div class="quality-card-head">
          <h3><Activity :size="16" />使用计数</h3>
          <span class="tag subtle">实时统计</span>
        </div>
        <div class="counts-grid">
          <div v-for="item in counts" :key="item.label">
            <strong>{{ number(item.value) }}</strong
            ><span>{{ item.label }}</span>
          </div>
        </div>
      </section>
      <div class="quality-disclaimer">
        <Info :size="15" />
        <div>
          <p>{{ quality.disclaimer }}</p>
          <p class="muted">
            生成时间 {{ dateText(quality.generated_at) }}；真实投档线不等于录取线，也不代表今年录取结果。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quality-area {
  min-height: 280px;
}
.quality-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: start;
}
.quality-wide {
  grid-column: span 2;
}
.quality-card {
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.quality-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.quality-card-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #3f5674;
}
.quality-card-head h3 > svg {
  color: #6c8fc6;
}
.coverage-title {
  font-size: 13px;
  font-weight: 500;
  color: #45668d;
}
.coverage-provinces {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.coverage-province {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #f7faff;
  border: 1px solid #e8eef8;
  border-radius: 7px;
  padding: 10px 12px;
  font-size: 10px;
  color: #7b8ca3;
}
.coverage-province strong {
  font-size: 12px;
  color: #3f5b7d;
}
.coverage-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 10px;
}
.simulated-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.simulated-grid > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #fafbfd;
  border: 1px solid #eef1f6;
  border-radius: 7px;
  padding: 10px 12px;
}
.simulated-grid strong {
  font-size: 16px;
  font-weight: 550;
  color: #4a6284;
}
.simulated-grid span {
  font-size: 9px;
  color: #98a4b5;
}
.version-table :deep(.el-table) {
  font-size: 11px;
}
.version-link {
  color: #4f7fbe;
  white-space: nowrap;
}
.version-link:hover {
  text-decoration: underline;
}
.patrol-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  padding: 7px 0;
  border-top: 1px dashed #eef1f6;
}
.patrol-row:first-of-type {
  border-top: 0;
}
.patrol-dataset {
  color: #526681;
  font-weight: 500;
}
.patrol-meta {
  font-size: 10px;
}
.patrol-ok {
  color: #6f9c84;
}
.patrol-bad {
  color: #cf7b7b;
}
.counts-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.counts-grid > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: #fafbfd;
  border: 1px solid #eef1f6;
  border-radius: 7px;
  padding: 9px 10px;
}
.counts-grid strong {
  font-size: 15px;
  font-weight: 550;
  color: #4a6284;
}
.counts-grid span {
  font-size: 9px;
  color: #98a4b5;
}
.quality-note {
  font-size: 10px;
  color: #9aa8ba;
  line-height: 1.8;
}
.popularity-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.popularity-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-top: 1px dashed #eef1f6;
  font-size: 11px;
}
.popularity-item:first-child {
  border-top: 0;
}
.popularity-rank {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  color: #98a4b5;
  background: #f3f6fa;
}
.popularity-rank.top {
  color: #9a8564;
  background: #f8f4ec;
}
.popularity-school {
  flex: 1;
  min-width: 0;
}
.popularity-school strong {
  font-weight: 500;
  color: #435a78;
  display: block;
}
.popularity-school p {
  font-size: 9px;
  color: #a2afc0;
  margin-top: 2px;
}
.popularity-count {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 550;
  color: #b06a74;
}
.popularity-count small {
  font-size: 9px;
  font-weight: 400;
  color: #a7b1bf;
  margin-left: 2px;
}
.quality-disclaimer {
  grid-column: span 2;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 10px;
  color: #98a4b5;
  line-height: 1.8;
  padding: 2px 4px;
}
.quality-disclaimer > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
@media (max-width: 1100px) {
  .quality-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .quality-wide,
  .quality-disclaimer {
    grid-column: span 1;
  }
  .coverage-provinces,
  .simulated-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
