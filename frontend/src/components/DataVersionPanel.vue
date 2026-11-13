<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { CheckCircle2, Database, Info, ShieldCheck, XCircle } from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import type { DataVersionItem, DataVersionList } from "../api/types";
import { number } from "../utils/format";

const data = ref<DataVersionList | null>(null);
const loading = ref(false);
const forbidden = ref(false);
const failed = ref(false);
const status = ref<"" | "pending" | "approved" | "rejected">("");
const FILTERS: { value: "" | "pending" | "approved" | "rejected"; label: string }[] = [
  { value: "", label: "全部" },
  { value: "pending", label: "待审核" },
  { value: "approved", label: "已通过" },
  { value: "rejected", label: "已驳回" },
];
const busyId = ref<number | null>(null);
const items = computed(() => data.value?.items ?? []);

async function load() {
  loading.value = true;
  forbidden.value = false;
  failed.value = false;
  try {
    data.value = (await api.dataVersions(status.value || undefined)).data;
  } catch (error: unknown) {
    const code = (error as { response?: { status?: number } })?.response?.status;
    if (code === 403) forbidden.value = true;
    else failed.value = true;
  } finally {
    loading.value = false;
  }
}

async function review(item: DataVersionItem, decision: "approved" | "rejected") {
  busyId.value = item.id;
  try {
    await api.reviewDataVersion(item.id, decision);
    ElMessage.success(decision === "approved" ? "已通过并发布为当前版本" : "已驳回该版本");
    await load();
  } catch {
    ElMessage.error("审核失败，请检查权限或稍后重试");
  } finally {
    busyId.value = null;
  }
}
function setStatus(value: "" | "pending" | "approved" | "rejected") {
  status.value = value;
  void load();
}
function timeText(value: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "—";
}
onMounted(load);
</script>

<template>
  <section class="panel quality-card quality-wide">
    <div class="quality-card-head">
      <h3><Database :size="16" />数据版本审核与发布</h3>
      <span class="tag subtle">仅管理员 · 通过即发布</span>
    </div>
    <p v-if="forbidden" class="quality-note">
      当前账号没有审核权限（仅管理员可查看与审核数据版本）。
    </p>
    <template v-else>
      <div v-if="data" class="version-summary">
        <span>共 <strong>{{ number(data.total) }}</strong> 个版本</span>
        <span class="tag warm">当前 {{ number(data.current) }}</span>
        <span class="tag">待审核 {{ number(data.counts.pending ?? 0) }}</span>
        <span class="tag">已通过 {{ number(data.counts.approved ?? 0) }}</span>
        <span class="tag">已驳回 {{ number(data.counts.rejected ?? 0) }}</span>
        <div class="version-filter">
          <button
            v-for="item in FILTERS"
            :key="item.value"
            type="button"
            :class="{ active: status === item.value }"
            @click="setStatus(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
      <el-table v-loading="loading" :data="items" size="small">
        <el-table-column label="数据集" min-width="110">
          <template #default="{ row }">
            <strong>{{ row.dataset }}</strong>
            <p class="table-sub">{{ row.parser_version }}</p>
          </template>
        </el-table-column>
        <el-table-column label="省份 / 年份" min-width="110">
          <template #default="{ row }">
            {{ [row.province, row.exam_year].filter(Boolean).join(" · ") || "—" }}
          </template>
        </el-table-column>
        <el-table-column label="行数" width="90">
          <template #default="{ row }">{{ number(row.row_count) }}</template>
        </el-table-column>
        <el-table-column label="审核状态" width="100">
          <template #default="{ row }">
            <span
              class="tag"
              :class="{
                warm: row.review_status === 'approved',
                reject: row.review_status === 'rejected',
              }"
              >{{ row.review_status_label }}</span
            >
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="90">
          <template #default="{ row }">
            <span v-if="row.is_current" class="tag warm">当前</span>
            <span v-else class="muted">历史</span>
          </template>
        </el-table-column>
        <el-table-column label="审核人 / 时间" min-width="150">
          <template #default="{ row }">
            <span class="muted">{{ row.reviewed_by || "—" }}</span>
            <p class="table-sub">{{ timeText(row.reviewed_at) }}</p>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              link
              :loading="busyId === row.id"
              @click="review(row, 'approved')"
              ><CheckCircle2 :size="13" />通过</el-button
            >
            <el-button
              size="small"
              type="danger"
              link
              :loading="busyId === row.id"
              @click="review(row, 'rejected')"
              ><XCircle :size="13" />驳回</el-button
            >
          </template>
        </el-table-column>
        <template #empty>暂无数据版本记录</template>
      </el-table>
      <p class="quality-note">
        <Info :size="12" />{{ failed ? "审核状态加载失败，可点击刷新重试。" : data?.note || "" }}
        通过即把该版本设为当前版本，同数据集同省份同年的旧版本自动转为历史版本（不删除数据）；审核动作写审计。
      </p>
    </template>
  </section>
</template>

<style scoped>
.version-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  font-size: 11px;
  color: #6d7f96;
}
.version-summary strong {
  color: #3f5674;
  font-weight: 600;
}
.version-filter {
  margin-left: auto;
  display: inline-flex;
  gap: 4px;
}
.version-filter button {
  font-size: 10px;
  color: #8b98aa;
  background: #f5f7fa;
  border: 1px solid #e8edf4;
  border-radius: 5px;
  padding: 4px 9px;
  cursor: pointer;
}
.version-filter button.active {
  color: #476a94;
  background: #eef4fb;
  border-color: #d4e3f3;
}
.tag.reject {
  color: #b4555f;
  background: #fdeef0;
}
.table-sub {
  margin-top: 2px;
  font-size: 9px;
  color: #9aa8ba;
}
.quality-note svg {
  vertical-align: -2px;
}
</style>
