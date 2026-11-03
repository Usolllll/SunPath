<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArrowRight,
  Download,
  Pencil,
  Trash2,
  Columns2,
  Plus,
  FolderHeart,
  Info,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import { useRouter } from "vue-router";
import { api } from "../api";
import type { Plan, Group } from "../api/types";
import { usePlanner } from "../stores/planner";
import { date, riskLabels, exportPlan, number } from "../utils/format";
import RiskBadge from "../components/RiskBadge.vue";
import GroupDrawer from "../components/GroupDrawer.vue";
const plans = ref<Plan[]>([]);
const busy = ref(false);
const failed = ref(false);
const selected = ref<number[]>([]);
const compareOpen = ref(false);
const preview = ref<Plan | null>(null);
const previewOpen = ref(false);
const detail = ref<Group | null>(null);
const drawer = ref(false);
const downloading = ref<number | null>(null);
const planner = usePlanner();
const router = useRouter();
const compared = computed(() =>
  plans.value.filter((p) => selected.value.includes(p.id)),
);
const tiers = (p: Plan, r: string) =>
  p.items.filter((g) => g.risk === r).length;
async function load() {
  busy.value = true;
  failed.value = false;
  try {
    plans.value = (await api.plans()).data;
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
async function edit(p: Plan) {
  if (planner.items.length) {
    try {
      await ElMessageBox.confirm(
        "打开此方案将替换当前本机草稿。是否继续？",
        "打开历史方案",
        { confirmButtonText: "继续编辑", cancelButtonText: "取消" },
      );
    } catch {
      return;
    }
  }
  planner.replace(
    JSON.parse(JSON.stringify(p.items)),
    p.id,
    p.name,
    p.profile_snapshot,
  );
  await router.push("/planner");
}
async function remove(p: Plan) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${p.name}”？此操作无法撤销。`,
      "删除方案",
      { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" },
    );
  } catch {
    return;
  }
  try {
    await api.deletePlan(p.id);
    selected.value = selected.value.filter((id) => id !== p.id);
    if (planner.editingId === p.id) planner.editingId = undefined;
    await load();
    ElMessage.success("方案已删除");
  } catch {
    /* API handles error */
  }
}
async function download(p: Plan) {
  downloading.value = p.id;
  try {
    await exportPlan(p.id);
    ElMessage.success("方案已导出为 CSV，可用 Excel 打开");
  } catch {
    /* API handles error */
  } finally {
    downloading.value = null;
  }
}
function toggle(id: number) {
  if (selected.value.includes(id))
    selected.value = selected.value.filter((i) => i !== id);
  else if (selected.value.length < 2) selected.value.push(id);
  else ElMessage.info("一次可对比两份方案，请先取消一份");
}
function show(g: Group) {
  detail.value = g;
  drawer.value = true;
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">YOUR PLANS, YOUR POSSIBILITIES</div>
      <h1>认真思考的选择，都值得被留下</h1>
      <p>查看历史方案，并排比较，在取舍中找到更清晰的方向。</p>
    </div>
    <div class="heading-actions">
      <el-button :disabled="selected.length !== 2" @click="compareOpen = true"
        ><Columns2 :size="16" />对比方案（{{ selected.length }}/2）</el-button
      ><el-button type="primary" size="large" @click="router.push('/planner')"
        ><Plus :size="16" />前往规划中心</el-button
      >
    </div>
  </div>
  <div v-loading="busy" class="plans-area">
    <div v-if="failed" class="empty-state">
      <p>方案加载失败</p>
      <el-button @click="load">重新加载</el-button>
    </div>
    <div v-else-if="plans.length" class="saved-plan-grid">
      <article
        v-for="plan in plans"
        :key="plan.id"
        :class="['panel saved-plan', { selected: selected.includes(plan.id) }]"
      >
        <div class="saved-plan-top">
          <span class="metric-icon blue"><FolderHeart :size="22" /></span
          ><el-checkbox
            :model-value="selected.includes(plan.id)"
            @change="toggle(plan.id)"
            >加入对比</el-checkbox
          >
        </div>
        <button
          class="plan-title"
          @click="
            preview = plan;
            previewOpen = true;
          "
        >
          {{ plan.name }}<ArrowRight :size="16" />
        </button>
        <p class="muted">
          {{ plan.profile_snapshot.province }} ·
          {{ plan.profile_snapshot.exam_year }} 届 ·
          {{ plan.profile_snapshot.score }} 分 ·
          {{ number(plan.profile_snapshot.rank) }} 位
        </p>
        <div class="saved-plan-count">
          <strong>{{ plan.items.length }}</strong
          ><span>个专业组</span>
          <div class="saved-tiers">
            <span v-for="(label, risk) in riskLabels" :key="risk" :class="risk"
              >{{ label.slice(0, 1) }} {{ tiers(plan, risk) }}</span
            >
          </div>
        </div>
        <p class="saved-time">最近保存 {{ date(plan.updated_at) }}</p>
        <div class="saved-plan-actions">
          <el-button @click="edit(plan)"><Pencil :size="14" />编辑</el-button
          ><el-button :loading="downloading === plan.id" @click="download(plan)"
            ><Download :size="14" />导出</el-button
          ><button
            class="icon-button danger"
            aria-label="删除方案"
            @click="remove(plan)"
          >
            <Trash2 :size="16" />
          </button>
        </div>
      </article>
    </div>
    <el-empty v-else description="还没有保存的方案，先为未来留下一份期待"
      ><el-button type="primary" @click="router.push('/analysis')"
        >开启智能匹配<ArrowRight :size="16" /></el-button
    ></el-empty>
  </div>
  <div class="data-disclaimer">
    <Info
      :size="15"
    />方案按保存时的考生画像与推荐结果存档。后续画像修改不会改变历史快照。全部为模拟数据。
  </div>
  <el-dialog
    v-model="compareOpen"
    title="志愿方案对比"
    width="min(1050px, 94vw)"
    ><div class="compare-grid">
      <section v-for="plan in compared" :key="plan.id" class="compare-column">
        <h2>{{ plan.name }}</h2>
        <p class="muted">
          {{ plan.profile_snapshot.province }} ·
          {{ plan.profile_snapshot.score }} 分 ·
          {{ number(plan.profile_snapshot.rank) }} 位
        </p>
        <div class="compare-summary">
          <span v-for="(label, risk) in riskLabels" :key="risk"
            ><RiskBadge :risk="risk" /> {{ tiers(plan, risk) }} 个</span
          >
        </div>
        <div
          v-for="(item, index) in plan.items"
          :key="item.id"
          class="compare-row"
          @click="show(item)"
        >
          <span>{{ index + 1 }}</span>
          <div>
            <strong>{{ item.university.name }}</strong>
            <p>{{ item.name }}</p>
          </div>
          <RiskBadge :risk="item.risk" short />
        </div>
      </section></div
  ></el-dialog>
  <el-dialog
    v-model="previewOpen"
    :title="preview?.name"
    width="min(850px, 94vw)"
    ><template v-if="preview"
      ><div class="notice compact">
        保存时画像：{{ preview.profile_snapshot.province }} ·
        {{ preview.profile_snapshot.exam_year }} 年 ·
        {{ preview.profile_snapshot.subjects.join(" / ") }} · 位次
        {{ number(preview.profile_snapshot.rank) }}
      </div>
      <el-table :data="preview.items" @row-click="show" class="clickable-table"
        ><el-table-column
          type="index"
          label="顺序"
          width="60"
        /><el-table-column label="院校" min-width="160"
          ><template #default="{ row }">{{
            row.university.name
          }}</template></el-table-column
        ><el-table-column
          prop="name"
          label="专业组"
          min-width="180"
        /><el-table-column label="梯度" width="90"
          ><template #default="{ row }"
            ><RiskBadge :risk="row.risk" /></template></el-table-column
        ><el-table-column label="参考位次" width="120"
          ><template #default="{ row }">{{
            number(row.baseline_rank)
          }}</template></el-table-column
        ></el-table
      >
      <p class="muted">
        点击任意专业组，查看保存时的完整分析与风险提示。
      </p></template
    ></el-dialog
  ><GroupDrawer v-model="drawer" :group="detail" />
</template>
