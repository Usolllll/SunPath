<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  ArrowUpRight,
  Database,
  Info,
  RotateCcw,
  Search,
  ShieldCheck,
} from "lucide-vue-next";
import type { RealDataRow, RealDataSummary } from "../api/types";
import { api } from "../api";
import { number } from "../utils/format";
import {
  REAL_DATA_PROVINCES,
  coverageText,
  safeSourceUrl,
  yearSpan,
} from "../utils/realdata";

interface VersionLink {
  key: string;
  label: string;
  url: string | null;
}
interface ProvinceCard {
  province: string;
  rows: number;
  schools: number;
  yearsText: string;
  published_at: string | null;
  versions: VersionLink[];
}

const summary = ref<RealDataSummary | null>(null);
const summaryLoading = ref(true);
const summaryFailed = ref(false);
const rows = ref<RealDataRow[]>([]);
const total = ref(0);
const busy = ref(false);
const failed = ref(false);
const unsupported = ref(false);
const filters = reactive({
  province: "辽宁",
  year: 2026 as number | null,
  q: "",
  page: 1,
  page_size: 50,
});

const provinceSummary = computed(
  () =>
    summary.value?.provinces.find(
      (item) => item.province === filters.province,
    ) ?? null,
);
const yearOptions = computed(() => {
  const years = provinceSummary.value?.years ?? [];
  return [...years].sort((a, b) => b - a);
});
const coverage = computed(() => coverageText(summary.value));
const provinceCards = computed<ProvinceCard[]>(() => {
  const order = (name: string) => {
    const index = REAL_DATA_PROVINCES.indexOf(
      name as (typeof REAL_DATA_PROVINCES)[number],
    );
    return index < 0 ? 99 : index;
  };
  return (summary.value?.provinces ?? [])
    .slice()
    .sort((a, b) => order(a.province) - order(b.province))
    .map((item) => ({
      province: item.province,
      rows: item.rows,
      schools: item.schools,
      yearsText: yearSpan(item.years),
      published_at: item.published_at,
      versions: (item.versions ?? []).map((version, index) => ({
        key: `${version.dataset}-${version.published_at ?? index}-${index}`,
        label: [
          version.dataset,
          version.published_at,
          version.row_count != null ? `${number(version.row_count)} 条` : null,
        ]
          .filter(Boolean)
          .join(" · "),
        url: safeSourceUrl(version.source_url),
      })),
    }));
});
const scopeText = computed(
  () => `仅收录 ${REAL_DATA_PROVINCES.join(" / ")} 三省考试院公开发布的投档数据`,
);

function sourceOf(url: string | null | undefined): string | null {
  return safeSourceUrl(url);
}
function cell(value: number | null | undefined): string {
  return value == null ? "未收录" : number(value);
}

let request = 0;
async function loadSummary() {
  summaryLoading.value = true;
  summaryFailed.value = false;
  try {
    summary.value = (await api.realDataSummary()).data;
  } catch {
    summary.value = null;
    summaryFailed.value = true;
  } finally {
    summaryLoading.value = false;
  }
}
async function loadRows() {
  const seq = ++request;
  busy.value = true;
  failed.value = false;
  unsupported.value = false;
  try {
    const params: {
      province: string;
      year?: number | null;
      q?: string;
      page?: number;
      page_size?: number;
    } = {
      province: filters.province,
      page: filters.page,
      page_size: filters.page_size,
    };
    if (filters.year) params.year = filters.year;
    const keyword = filters.q.trim();
    if (keyword) params.q = keyword;
    const { data } = await api.realDataRows(params);
    if (seq !== request) return;
    rows.value = data.items ?? [];
    total.value = data.total ?? 0;
  } catch (error) {
    if (seq !== request) return;
    rows.value = [];
    total.value = 0;
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    if (status === 422) unsupported.value = true;
    else failed.value = true;
  } finally {
    if (seq === request) busy.value = false;
  }
}
function latestYear(province: string): number | null {
  const item = summary.value?.provinces.find(
    (entry) => entry.province === province,
  );
  const years = item?.years ?? [];
  return years.length ? Math.max(...years) : null;
}
function onProvinceChange() {
  filters.year = latestYear(filters.province);
  filters.page = 1;
  void loadRows();
}
function selectProvince(province: string) {
  filters.province = province;
  onProvinceChange();
}
function onYearChange() {
  filters.page = 1;
  void loadRows();
}
function onPageSizeChange() {
  filters.page = 1;
  void loadRows();
}
function search() {
  filters.page = 1;
  void loadRows();
}
function reset() {
  filters.q = "";
  filters.year = latestYear(filters.province);
  filters.page = 1;
  void loadRows();
}
async function onMountedLoad() {
  await loadSummary();
  const available = summary.value?.provinces ?? [];
  if (available.length && !available.some((p) => p.province === filters.province)) {
    const first = available.find((p) =>
      REAL_DATA_PROVINCES.includes(
        p.province as (typeof REAL_DATA_PROVINCES)[number],
      ),
    );
    filters.province = first?.province ?? available[0].province;
  }
  filters.year = latestYear(filters.province);
  await loadRows();
}
onMounted(onMountedLoad);
</script>

<template>
  <div class="realdata">
    <div
      v-loading="summaryLoading"
      element-loading-text="正在读取官方数据版本…"
      class="freshness"
    >
      <div class="freshness-head">
        <span class="realdata-badge"
          ><ShieldCheck :size="13" />官方原始数据 · 真实投档</span
        >
        <strong class="freshness-title">{{ coverage }}</strong>
        <span class="freshness-note"
          >来自各省教育考试院公开文件，与下方模拟样本库分开存放</span
        >
      </div>
      <p v-if="summaryFailed" class="freshness-error">
        <Info :size="13" />数据版本信息暂时无法获取，下方明细仍可查询。
      </p>
      <div v-else class="freshness-list">
        <article
          v-for="card in provinceCards"
          :key="card.province"
          class="freshness-item"
        >
          <div class="freshness-item-head">
            <strong>{{ card.province }}</strong>
            <span class="tag"
              >{{ number(card.rows) }} 条 · {{ number(card.schools) }} 所</span
            >
            <span class="tag subtle">{{ card.yearsText }}</span>
          </div>
          <p class="freshness-meta">
            数据发布：{{ card.published_at || "未标注" }}
          </p>
          <div class="freshness-links">
            <a
              v-for="version in card.versions.filter((item) => item.url)"
              :key="version.key"
              :href="version.url || '#'"
              target="_blank"
              rel="noopener noreferrer"
              class="freshness-link"
              :title="`${version.label} · 打开省考试院公告`"
              >查看公告 ↗ <span>{{ version.label }}</span></a
            >
            <span v-if="!card.versions.length" class="muted"
              >公告链接未收录</span
            >
          </div>
        </article>
      </div>
      <p v-if="summary?.note" class="freshness-footnote">
        <Database :size="12" />{{ summary.note }}
      </p>
    </div>

    <form class="filter-toolbar realdata-filters" @submit.prevent="search">
      <el-select
        v-model="filters.province"
        placeholder="省份"
        aria-label="官方数据省份"
        @change="onProvinceChange"
        ><el-option
          v-for="province in REAL_DATA_PROVINCES"
          :key="province"
          :value="province"
          :label="province"
        /></el-select>
      <el-select
        v-model="filters.year"
        clearable
        placeholder="全部年份"
        aria-label="官方数据年份"
        @change="onYearChange"
        ><el-option
          v-for="year in yearOptions"
          :key="year"
          :value="year"
          :label="`${year} 年`" /></el-select
      ><el-input
        v-model="filters.q"
        placeholder="校名搜索（如：东北大学）"
        clearable
        aria-label="校名搜索"
        @clear="search"
        ><template #prefix><Search :size="16" /></template></el-input
      ><el-button type="primary" native-type="submit">查询</el-button
      ><el-button @click="reset" aria-label="重置筛选"
        ><RotateCcw :size="15"
      /></el-button>
    </form>

    <div class="realdata-meta">
      <span class="realdata-count"
        >官方投档记录 <strong>{{ number(total) }}</strong> 条</span
      >
      <span
        >{{ filters.province }} · {{ filters.year ? `${filters.year} 年` : "全部年份" }}</span
      >
      <span class="realdata-scope">{{ scopeText }}</span>
      <label class="realdata-page-size"
        >每页<el-select
          v-model="filters.page_size"
          size="small"
          aria-label="每页条数"
          @change="onPageSizeChange"
          ><el-option
            v-for="size in [20, 50, 100]"
            :key="size"
            :value="size"
            :label="`${size} 条`" /></el-select
      ></label>
    </div>

    <div
      v-loading="busy"
      element-loading-text="正在读取官方投档数据…"
      class="realdata-table"
    >
      <div v-if="unsupported" class="empty-state">
        <p>该省官方数据尚未收录</p>
        <p class="muted">
          目前仅收录 {{ REAL_DATA_PROVINCES.join(" / ") }} 三省考试院公开发布的投档数据。
        </p>
        <el-button @click="selectProvince('辽宁')">查看辽宁数据</el-button>
      </div>
      <div v-else-if="failed" class="empty-state">
        <p>官方数据加载失败</p>
        <el-button @click="loadRows">重新加载</el-button>
      </div>
      <el-table v-else :data="rows" size="small" class="realdata-table-grid">
        <el-table-column label="学校" min-width="150"
          ><template #default="{ row }"
            ><strong>{{ row.school_name }}</strong></template
          ></el-table-column
        >
        <el-table-column label="年份" width="72"
          ><template #default="{ row }">{{ row.exam_year }}</template></el-table-column
        >
        <el-table-column label="科类" width="92"
          ><template #default="{ row }"
            ><span>{{ row.subject_type || "未标注" }}</span>
            <p v-if="row.round_no" class="table-sub">{{ row.round_no }}</p></template
          ></el-table-column
        >
        <el-table-column label="专业 / 专业组" min-width="230"
          ><template #default="{ row }"
            ><strong>{{
              row.major_name || row.group_name || "专业未标注"
            }}</strong>
            <p
              v-if="row.group_name && row.group_name !== row.major_name"
              class="table-sub"
            >
              专业组：{{ row.group_name }}
            </p>
            <p v-if="row.required_subjects" class="table-sub">
              选科：{{ row.required_subjects }}
            </p></template
          ></el-table-column
        >
        <el-table-column label="最低分" width="82"
          ><template #default="{ row }">{{ cell(row.min_score) }}</template></el-table-column
        >
        <el-table-column label="最低位次" width="96"
          ><template #default="{ row }">{{ cell(row.min_rank) }}</template></el-table-column
        >
        <el-table-column label="来源" width="88"
          ><template #default="{ row }"
            ><a
              v-if="sourceOf(row.source_url)"
              :href="sourceOf(row.source_url) || '#'"
              target="_blank"
              rel="noopener noreferrer"
              class="source-link"
              :title="`来源公告 ${row.published_at || '发布时间未标注'}`"
              >来源 <ArrowUpRight :size="12" /></a
            ><span v-else class="muted">未收录</span></template
          ></el-table-column
        >
        <el-table-column label="发布时间" width="102"
          ><template #default="{ row }">{{
            row.published_at || "未标注"
          }}</template></el-table-column
        >
        <template #empty
          >暂无符合条件的官方投档记录，可更换年份、校名关键词或省份</template
        >
      </el-table>
    </div>

    <div class="pagination-row realdata-pagination">
      <span>真实投档数据 · 仅作核对参考，不代表今年录取结果</span
      ><el-pagination
        v-model:current-page="filters.page"
        :page-size="filters.page_size"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadRows"
      />
    </div>

    <div class="realdata-disclaimer">
      <Info :size="15" />
      <div>
        <p>
          <strong>真实投档线不等于录取线</strong>，不代表今年录取结果；正式填报以省考试院当年公布为准。
        </p>
        <p class="muted">
          官方投档数据与「高校信息 / 专业信息 / 历年录取 / 招生计划」中的模拟样本库分开存放，不混用、不推测。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.realdata {
  padding: 20px 24px 0;
}
.freshness {
  border: 1px solid #e3ecf9;
  background: #f7faff;
  border-radius: 9px;
  padding: 15px 17px 13px;
}
.freshness-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.realdata-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: #4a7c63;
  background: #edf7f1;
  border: 1px solid #d6ecdf;
  border-radius: 4px;
  padding: 3px 8px;
  white-space: nowrap;
}
.freshness-title {
  font-size: 12px;
  font-weight: 500;
  color: #45668d;
}
.freshness-note {
  font-size: 10px;
  color: #93a3b8;
}
.freshness-error {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #98a4b5;
  margin-top: 9px;
}
.freshness-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 10px;
  margin-top: 11px;
}
.freshness-item {
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 7px;
  padding: 10px 12px;
}
.freshness-item-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.freshness-item-head strong {
  font-size: 12px;
  color: #3f5b7d;
}
.freshness-meta {
  font-size: 9px;
  color: #9aa8ba;
  margin-top: 7px;
}
.freshness-links {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
}
.freshness-link {
  font-size: 10px;
  color: #4f7fbe;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.freshness-link:hover {
  color: #2f5fa3;
  text-decoration: underline;
}
.freshness-link span {
  color: #9aa8ba;
  font-size: 9px;
}
.freshness-footnote {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  color: #9fabbc;
  margin-top: 10px;
}
.realdata-filters {
  display: flex;
  gap: 10px;
  padding: 18px 0 12px;
}
.realdata-filters > .el-select {
  flex: 0 0 118px;
  min-width: 118px;
}
.realdata-filters > .el-input {
  flex: 1;
  min-width: 160px;
}
.realdata-filters > .el-button {
  height: 34px;
  margin-left: 0;
}
.realdata-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 0 0 12px;
  font-size: 10px;
  color: #98a4b5;
}
.realdata-count strong {
  color: #476a94;
  font-weight: 600;
}
.realdata-scope {
  color: #a7b1bf;
}
.realdata-page-size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 10px;
}
.realdata-page-size .el-select {
  width: 84px;
}
.realdata-table {
  border: 1px solid var(--line);
  border-radius: 8px;
  min-height: 220px;
}
.realdata-table :deep(.el-table) {
  font-size: 11px;
}
.realdata-table :deep(.el-table strong) {
  font-weight: 500;
  color: #3f5674;
}
.realdata-table :deep(.el-table .cell) {
  line-height: 1.55;
}
.source-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: #4f7fbe;
  white-space: nowrap;
}
.source-link:hover {
  color: #2f5fa3;
  text-decoration: underline;
}
.realdata-pagination {
  padding: 14px 2px;
}
.realdata-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border-top: 1px solid var(--line);
  padding: 14px 2px 20px;
  font-size: 10px;
  color: #98a4b5;
  line-height: 1.8;
}
.realdata-disclaimer > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.realdata-disclaimer p {
  margin: 0;
}
.realdata-disclaimer strong {
  color: #7d8ea6;
  font-weight: 600;
}
.realdata-disclaimer .muted {
  margin-top: 3px;
}
@media (max-width: 900px) {
  .realdata {
    padding: 16px 16px 0;
  }
  .realdata-filters {
    flex-wrap: wrap;
  }
  .realdata-filters > .el-input {
    flex: 1 1 100%;
    order: -1;
  }
  .realdata-page-size {
    margin-left: 0;
  }
}
</style>
