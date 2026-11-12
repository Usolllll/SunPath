<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  CalendarClock,
  Download,
  Info,
  RefreshCw,
  Send,
  Sparkles,
  Timer,
} from "lucide-vue-next";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import type {
  ProcessCollection,
  ProcessResults,
  ProcessSchedule,
  Plan,
} from "../api/types";
import { useAuth } from "../stores/auth";
import { number, exportProcessResults } from "../utils/format";
import {
  collectionCountdown,
  collectionStatusLabel,
  collectionTone,
  processStateClass,
  processStateLabel,
  summaryText,
  updatedAtText,
  verdictClass,
  verdictLabel,
  windowText,
} from "../utils/process";
import RiskBadge from "../components/RiskBadge.vue";
const router = useRouter();
const auth = useAuth();
const provinces = ["浙江", "江苏", "山东", "广东", "河南", "四川"];
const province = ref(auth.user?.profile?.province || "浙江");
const schedule = ref<ProcessSchedule | null>(null);
const scheduleBusy = ref(false);
const scheduleFailed = ref(false);
const collection = ref<ProcessCollection | null>(null);
const collectionBusy = ref(false);
const plans = ref<Plan[]>([]);
const plansBusy = ref(false);
const selectedPlanId = ref<number | null>(null);
const results = ref<ProcessResults | null>(null);
const resultsBusy = ref(false);
const resultsFailed = ref(false);
const exporting = ref(false);
const collectionDays = computed(() => collectionCountdown(collection.value));
const collectionClass = computed(() =>
  collectionTone(collection.value?.days_left, collection.value?.status),
);
const resultLine = computed(() =>
  results.value
    ? `${summaryText(results.value.summary)} · 你的位次 ${number(results.value.profile_rank)}`
    : "",
);

async function loadSchedule() {
  scheduleBusy.value = true;
  scheduleFailed.value = false;
  try {
    schedule.value = (
      await api.processSchedule(province.value)
    ).data;
  } catch {
    scheduleFailed.value = true;
  } finally {
    scheduleBusy.value = false;
  }
}
async function loadCollection() {
  collectionBusy.value = true;
  try {
    collection.value = (await api.processCollection(province.value)).data;
  } catch {
    collection.value = null;
  } finally {
    collectionBusy.value = false;
  }
}
async function loadResults() {
  if (!selectedPlanId.value) {
    results.value = null;
    return;
  }
  resultsBusy.value = true;
  resultsFailed.value = false;
  try {
    results.value = (await api.processResults(selectedPlanId.value)).data;
  } catch {
    results.value = null;
    resultsFailed.value = true;
  } finally {
    resultsBusy.value = false;
  }
}
async function loadPlans() {
  plansBusy.value = true;
  try {
    plans.value = (await api.plans()).data;
    if (!plans.value.length) {
      selectedPlanId.value = null;
      results.value = null;
      return;
    }
    const current = plans.value.find(
      (plan) => plan.id === selectedPlanId.value,
    );
    selectedPlanId.value = current?.id ?? plans.value[0].id;
    await loadResults();
  } catch {
    plans.value = [];
  } finally {
    plansBusy.value = false;
  }
}
function onProvinceChange() {
  void loadSchedule();
  void loadCollection();
}
function refreshAll() {
  void loadSchedule();
  void loadCollection();
  void loadPlans();
}
async function exportResults() {
  if (!selectedPlanId.value || !results.value) return;
  exporting.value = true;
  try {
    const filename = await exportProcessResults(selectedPlanId.value);
    ElMessage.success(`已导出 ${filename}`);
  } catch {
    /* API 拦截器已提示 */
  } finally {
    exporting.value = false;
  }
}
onMounted(() => {
  void loadSchedule();
  void loadCollection();
  void loadPlans();
});
</script>

<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">TRACK EVERY KEY DATE</div>
      <h1>把录取进程，放在同一张时间表上</h1>
      <p>
        批次时间轴、征集志愿窗口与模拟投档结果都集中在录取进程页；模拟投档只按官方投档最低位次演示判定。
      </p>
    </div>
    <div class="heading-actions">
      <el-select
        v-model="province"
        class="province-select"
        aria-label="生源省份"
        @change="onProvinceChange"
      >
        <el-option
          v-for="item in provinces"
          :key="item"
          :value="item"
          :label="item"
        />
      </el-select>
      <el-button :loading="scheduleBusy" @click="refreshAll"
        ><RefreshCw :size="15" />刷新</el-button
      >
    </div>
  </div>

  <section class="panel process-panel" v-loading="scheduleBusy">
    <div class="process-head">
      <div>
        <h3>
          <CalendarClock :size="17" />{{ province }} · 2026 录取进程
        </h3>
        <p>
          共 {{ schedule?.batches.length || 0 }} 个批次 ·
          {{ updatedAtText(schedule?.updated_at) }}
        </p>
      </div>
      <span class="tag subtle">时间轴为演示口径</span>
    </div>
    <div v-if="scheduleFailed" class="empty-state">
      <p>录取进程加载失败</p>
      <el-button @click="loadSchedule">重新加载</el-button>
    </div>
    <div v-else-if="schedule?.batches.length" class="batch-grid">
      <article
        v-for="batch in schedule.batches"
        :key="batch.batch"
        class="batch-card"
      >
        <div class="batch-head">
          <strong>{{ batch.batch }}</strong>
          <span v-if="batch.current_stage" class="tag warm"
            >当前：{{ batch.current_stage }}</span
          >
          <span v-else class="tag subtle">尚未开始</span>
        </div>
        <p v-if="batch.next_window" class="batch-next">
          <Timer :size="12" />下一窗口：{{ batch.next_window }}
        </p>
        <ol v-if="batch.events.length" class="process-timeline">
          <li
            v-for="event in batch.events"
            :key="`${batch.batch}-${event.stage}`"
            :class="[`state-${processStateClass(event.state)}`]"
          >
            <span class="timeline-dot"></span>
            <div class="timeline-body">
              <div class="timeline-title">
                <strong>{{ event.stage }}</strong
                ><span class="timeline-state">{{
                  processStateLabel(event.state)
                }}</span>
              </div>
              <p>{{ windowText(event.start, event.end) }}</p>
            </div>
          </li>
        </ol>
        <p v-else class="muted">该批次暂无时间节点。</p>
      </article>
    </div>
    <el-empty v-else description="暂无可展示的录取进程"></el-empty>
    <p v-if="schedule?.note" class="process-note">
      <Info :size="13" />{{ schedule.note }}
    </p>
  </section>

  <div class="process-columns">
    <section class="panel collection-card" v-loading="collectionBusy">
      <div class="collection-head">
        <h3><Timer :size="16" />征集志愿</h3>
        <span class="tag subtle">{{ collection?.batch || "待公布" }}</span>
      </div>
      <template v-if="collection">
        <p class="collection-days" :class="collectionClass">
          {{ collectionDays }}
        </p>
        <p class="collection-window">
          {{ windowText(collection.start, collection.end) }}
        </p>
        <p v-if="collection.status" class="collection-status">
          状态：{{ collectionStatusLabel(collection.status) }}
        </p>
        <p class="collection-note">{{ collection.note }}</p>
      </template>
      <p v-else class="muted">暂无征集志愿信息。</p>
      <p class="collection-tip">
        征集志愿时间以省考试院公告为准；倒计时只作提醒，不构成填报建议。
      </p>
    </section>

    <section class="panel results-panel">
      <div class="results-head">
        <div>
          <h3><Send :size="16" />模拟投档结果</h3>
          <p>按已保存方案逐条比对官方真实投档最低位次</p>
        </div>
        <div class="results-actions">
          <el-select
            v-model="selectedPlanId"
            placeholder="选择我的方案"
            :disabled="!plans.length || plansBusy"
            aria-label="选择志愿方案"
            @change="loadResults"
          >
            <el-option
              v-for="plan in plans"
              :key="plan.id"
              :value="plan.id"
              :label="`${plan.name}（${plan.items.length} 个专业组）`"
            />
          </el-select>
          <el-button
            :loading="exporting"
            :disabled="!selectedPlanId || !results"
            @click="exportResults"
            ><Download :size="15" />导出结果 CSV</el-button
          >
        </div>
      </div>
      <div v-if="plansBusy" class="results-loading"></div>
      <div v-else-if="!plans.length" class="empty-state">
        <p>还没有保存的方案，先保存一份方案再查看模拟投档结果</p>
        <el-button type="primary" @click="router.push('/planner')"
          ><Sparkles :size="14" />去规划中心</el-button
        >
      </div>
      <div v-else v-loading="resultsBusy" class="results-body">
        <div v-if="resultsFailed" class="empty-state">
          <p>模拟投档结果加载失败</p>
          <el-button @click="loadResults">重新加载</el-button>
        </div>
        <template v-else-if="results">
          <div class="result-summary">
            <div class="summary-cell total">
              <strong>{{ results.summary.total }}</strong><span>条志愿</span>
            </div>
            <div class="summary-cell pass">
              <strong>{{ results.summary.pass }}</strong
              ><span>达到近一次投档线</span>
            </div>
            <div class="summary-cell fail">
              <strong>{{ results.summary.fail }}</strong
              ><span>未达到近一次投档线</span>
            </div>
            <div class="summary-cell nodata">
              <strong>{{ results.summary.no_data }}</strong
              ><span>暂无官方数据</span>
            </div>
          </div>
          <p class="result-line">{{ resultLine }}</p>
          <el-table :data="results.items" size="small" class="result-table">
            <el-table-column label="序号" width="58"
              ><template #default="{ row }">{{
                row.position
              }}</template></el-table-column
            >
            <el-table-column label="院校" min-width="150"
              ><template #default="{ row }"
                ><strong>{{ row.university }}</strong></template
              ></el-table-column
            >
            <el-table-column label="专业组" min-width="170"
              ><template #default="{ row }">{{ row.group_name }}</template></el-table-column
            >
            <el-table-column label="梯度" width="88"
              ><template #default="{ row }"
                ><RiskBadge :risk="row.risk" /></template></el-table-column
            >
            <el-table-column label="你的位次" width="100"
              ><template #default="{ row }">{{
                number(row.user_rank)
              }}</template></el-table-column
            >
            <el-table-column label="官方最低位次" width="112"
              ><template #default="{ row }">{{
                row.official?.min_rank != null
                  ? number(row.official.min_rank)
                  : "未收录"
              }}</template></el-table-column
            >
            <el-table-column label="年份" width="78"
              ><template #default="{ row }">{{
                row.official?.exam_year ?? "—"
              }}</template></el-table-column
            >
            <el-table-column label="判定" min-width="210"
              ><template #default="{ row }"
                ><span :class="['verdict-tag', verdictClass(row.verdict)]">{{
                  row.label || verdictLabel(row.verdict)
                }}</span></template
              ></el-table-column
            >
            <template #empty>该方案暂无投档结果</template>
          </el-table>
        </template>
        <el-empty v-else description="选择方案后查看模拟投档结果" />
      </div>
    </section>
  </div>

  <div class="data-disclaimer">
    <Info :size="15" />{{
      results?.disclaimer ||
      "模拟投档仅按官方真实投档最低位次演示判定，不代表录取结果或概率；正式录取以省考试院公布为准。"
    }}
  </div>
</template>

<style scoped>
.province-select {
  width: 108px;
}
.process-panel {
  padding: 21px 23px 18px;
}
.process-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.process-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #46618a;
}
.process-head h3 > svg {
  color: #6c8fc6;
}
.process-head p {
  font-size: 10px;
  color: #98a4b5;
  margin-top: 6px;
}
.batch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.batch-card {
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fbfcfe;
  padding: 15px 16px;
}
.batch-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.batch-head strong {
  font-size: 13px;
  color: #3f5674;
}
.batch-next {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: #8b9bb1;
  margin-top: 7px;
}
.process-timeline {
  list-style: none;
  margin: 13px 0 0;
  padding: 0 0 0 2px;
}
.process-timeline > li {
  position: relative;
  padding: 0 0 15px 22px;
}
.process-timeline > li:last-child {
  padding-bottom: 0;
}
.process-timeline > li:not(:last-child):before {
  content: "";
  position: absolute;
  left: 4px;
  top: 12px;
  bottom: 0;
  width: 1px;
  background: #e4eaf3;
}
.timeline-dot {
  position: absolute;
  left: 0;
  top: 5px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #dfe6f0;
  border: 2px solid #fbfcfe;
  box-shadow: 0 0 0 1px #dfe6f0;
}
.process-timeline > li.state-done .timeline-dot {
  background: #7fa98f;
  box-shadow: 0 0 0 1px #7fa98f;
}
.process-timeline > li.state-active .timeline-dot {
  background: #d9a05e;
  box-shadow:
    0 0 0 1px #d9a05e,
    0 0 0 4px #fbf3e6;
}
.process-timeline > li.state-upcoming .timeline-dot {
  background: #c8d2e0;
  box-shadow: 0 0 0 1px #c8d2e0;
}
.timeline-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.timeline-title strong {
  font-size: 11px;
  font-weight: 500;
  color: #4d6484;
}
.timeline-state {
  font-size: 9px;
  border-radius: 3px;
  padding: 1px 5px;
  background: #f1f4f9;
  color: #93a1b3;
}
.process-timeline > li.state-done .timeline-state {
  background: #edf6f0;
  color: #5d8a72;
}
.process-timeline > li.state-active .timeline-state {
  background: #fdf4e7;
  color: #a97d45;
}
.timeline-body > p {
  font-size: 9px;
  color: #9aa8ba;
  margin-top: 4px;
}
.timeline-status {
  color: #a8b3c2 !important;
}
.process-note {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  font-size: 9px;
  color: #9aa8ba;
  line-height: 1.8;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #eef1f6;
}
.process-columns {
  display: grid;
  grid-template-columns: minmax(250px, 0.62fr) minmax(0, 1.9fr);
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}
.collection-card {
  padding: 19px 20px;
}
.collection-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.collection-head h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #46618a;
}
.collection-head h3 > svg {
  color: #c79a5f;
}
.collection-days {
  font-size: 27px;
  font-weight: 550;
  color: #4a6284;
  margin-top: 15px;
}
.collection-days.urgent {
  color: #c47d4d;
}
.collection-days.ended,
.collection-days.pending {
  color: #98a4b5;
  font-size: 22px;
}
.collection-window {
  font-size: 11px;
  color: #6f819b;
  margin-top: 6px;
}
.collection-status {
  font-size: 10px;
  color: #93a1b3;
  margin-top: 4px;
}
.collection-note {
  font-size: 10px;
  color: #98a4b5;
  line-height: 1.8;
  margin-top: 10px;
}
.collection-tip {
  font-size: 9px;
  color: #a9b3c1;
  line-height: 1.8;
  margin-top: 14px;
  padding-top: 11px;
  border-top: 1px dashed #eef1f6;
}
.results-panel {
  padding: 19px 20px;
  min-width: 0;
}
.results-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.results-head h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  color: #46618a;
}
.results-head h3 > svg {
  color: #6c8fc6;
}
.results-head p {
  font-size: 10px;
  color: #98a4b5;
  margin-top: 5px;
}
.results-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.results-actions .el-select {
  width: 210px;
}
.results-body {
  margin-top: 15px;
  min-height: 180px;
}
.result-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.summary-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  border: 1px solid #eef1f6;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fafbfd;
}
.summary-cell strong {
  font-size: 18px;
  font-weight: 550;
  color: #4a6284;
}
.summary-cell span {
  font-size: 9px;
  color: #98a4b5;
}
.summary-cell.pass strong {
  color: #5d8a72;
}
.summary-cell.fail strong {
  color: #8b97a8;
}
.summary-cell.nodata strong {
  color: #b08a52;
}
.result-line {
  font-size: 10px;
  color: #8b9bb1;
  margin: 12px 0 10px;
}
.result-table :deep(.el-table) {
  font-size: 11px;
}
.verdict-tag {
  display: inline-flex;
  align-items: center;
  font-size: 9px;
  line-height: 18px;
  padding: 0 7px;
  border-radius: 3px;
  white-space: nowrap;
}
.verdict-tag.pass {
  color: #557f68;
  background: #edf6f0;
}
.verdict-tag.fail {
  color: #7c8899;
  background: #f1f3f7;
}
.verdict-tag.no-data {
  color: #9c7a3f;
  background: #fbf3e5;
}
.results-loading {
  height: 120px;
}
@media (max-width: 1100px) {
  .process-columns {
    grid-template-columns: minmax(0, 1fr);
  }
  .result-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
