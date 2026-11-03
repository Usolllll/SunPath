<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import axios from "axios";
import {
  ArrowRight,
  Sparkles,
  SlidersHorizontal,
  Check,
  Info,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import { useRouter } from "vue-router";
import { api } from "../api";
import type { Group, Recommendation } from "../api/types";
import { useAuth } from "../stores/auth";
import { usePlanner } from "../stores/planner";
import { number, riskLabels } from "../utils/format";
import SchoolCard from "../components/SchoolCard.vue";
import GroupDrawer from "../components/GroupDrawer.vue";
const auth = useAuth();
const planner = usePlanner();
const router = useRouter();
const busy = ref(false);
const aiBusy = ref(false);
const aiFailed = ref(false);
const matchCount = ref(12);
const validCount = computed(
  () =>
    Number.isInteger(matchCount.value) &&
    matchCount.value >= 3 &&
    matchCount.value <= 30,
);
let controller: AbortController | undefined;
const generating = ref(false);
const failed = ref(false);
const tab = ref("all");
const region = ref("");
const keyword = ref("");
const data = ref<Recommendation>({
  items: [],
  counts: { reach: 0, steady: 0, safe: 0 },
  disclaimer: "",
  engine_version: "",
});
const detail = ref<Group | null>(null);
const drawer = ref(false);
const filtered = computed(() =>
  data.value.items.filter(
    (g) =>
      (tab.value === "all" || g.risk === tab.value) &&
      (!region.value || g.university.region === region.value) &&
      (!keyword.value ||
        `${g.university.name} ${g.majors.join(" ")}`.includes(keyword.value)),
  ),
);
const regions = computed(() => [
  ...new Set(data.value.items.map((g) => g.university.region)),
]);
async function load() {
  if (!auth.user?.profile || aiBusy.value) return;
  busy.value = true;
  failed.value = false;
  aiFailed.value = false;
  try {
    data.value = (await api.recommendations()).data;
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
async function runAi() {
  if (aiBusy.value || busy.value || !auth.user?.profile) return;
  if (
    !Number.isInteger(matchCount.value) ||
    matchCount.value < 3 ||
    matchCount.value > 30
  )
    return ElMessage.warning("请选择 3–30 个专业组");
  aiBusy.value = true;
  failed.value = false;
  aiFailed.value = false;
  controller = new AbortController();
  try {
    data.value = (await api.aiMatch(matchCount.value, controller.signal)).data;
    if (data.value.ai_selection?.below_minimum)
      ElMessage.warning(data.value.ai_selection.message);
    else ElMessage.success("AI 精选完成，全部结果已通过数据库与规则校验");
  } catch (error) {
    if (!axios.isCancel(error)) {
      failed.value = true;
      aiFailed.value = true;
    }
  } finally {
    aiBusy.value = false;
    controller = undefined;
  }
}
async function generate() {
  if (busy.value || aiBusy.value || generating.value || failed.value) return;
  if (!data.value.ai_selection)
    return ElMessage.warning("请先完成 AI 匹配，再生成志愿方案");
  if (!validCount.value) return ElMessage.warning("请选择 3–30 个专业组");
  if (
    data.value.ai_selection &&
    data.value.ai_selection.requested_count !== matchCount.value
  )
    return ElMessage.warning("推荐数量已调整，请重新 AI 匹配");
  if (planner.items.length) {
    try {
      await ElMessageBox.confirm(
        "重新生成将替换当前草稿，已保存方案不会受影响。",
        "生成新方案",
        { confirmButtonText: "重新生成", cancelButtonText: "取消" },
      );
    } catch {
      return;
    }
  }
  generating.value = true;
  try {
    const response = {
      items: data.value.items,
      missing_tiers: data.value.ai_selection.missing_tiers,
    };
    if (!response.items.length)
      return ElMessage.warning(
        "当前画像暂无可用候选，请调整画像或浏览招生数据",
      );
    planner.replace([...response.items]);
    if (response.missing_tiers.length)
      ElMessage.warning(
        `当前样本缺少${response.missing_tiers.map((r) => riskLabels[r as keyof typeof riskLabels]).join("、")}梯度，请审慎调整`,
      );
    else ElMessage.success("已生成冲稳保方案，可以继续调整顺序");
    await router.push("/planner");
  } catch {
    /* API handles error */
  } finally {
    generating.value = false;
  }
}
function show(group: Group) {
  detail.value = group;
  drawer.value = true;
}
onMounted(load);
onBeforeUnmount(() => controller?.abort());
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">DATA-INFORMED, HUMAN-CENTERED</div>
      <h1>找到与你同频的大学</h1>
      <p>以位次为起点，以热爱为方向。每一条推荐，都有据可循。</p>
    </div>
    <el-button
      v-if="auth.user?.profile"
      type="primary"
      size="large"
      :loading="generating"
      :disabled="
        !data.items.length ||
        !data.ai_selection ||
        busy ||
        aiBusy ||
        failed ||
        !validCount ||
        !!(
          data.ai_selection && data.ai_selection.requested_count !== matchCount
        )
      "
      @click="generate"
      ><Sparkles :size="17" />生成志愿方案</el-button
    >
  </div>
  <template v-if="auth.user?.profile"
    ><section class="analysis-profile panel">
      <div class="analysis-profile-icon"><Sparkles :size="25" /></div>
      <div>
        <h3>
          {{ auth.user.profile.province }} ·
          {{ auth.user.profile.exam_year }} 届 ·
          {{ auth.user.profile.score }} 分<span class="analysis-rank"
            >全省 {{ number(auth.user.profile.rank) }} 位</span
          >
        </h3>
        <p>
          {{ auth.user.profile.subjects.join(" / ") }}<span>·</span>偏好地区：{{
            auth.user.profile.regions.join("、") || "不限"
          }}
        </p>
      </div>
      <RouterLink to="/profile" class="text-button"
        ><SlidersHorizontal :size="15" />调整画像</RouterLink
      >
    </section>
    <section class="panel ai-match-controls">
      <div>
        <h3>
          <Sparkles :size="17" />AI 院校精选
          <span class="tag warm">数据库约束</span>
        </h3>
        <p>
          将考生画像与已收录院校资料交给 DeepSeek，按偏好挑选；后端校验
          ID、选科、位次、人数和梯度。
        </p>
        <small
          >录取与计划为模拟样本；AI
          不会添加库外院校，也不能修改录取数据。</small
        >
      </div>
      <div class="ai-match-actions">
        <label
          >推荐数量<el-input-number
            v-model="matchCount"
            :min="3"
            :max="30"
            :step="1"
            controls-position="right"
            :disabled="aiBusy"
            aria-label="AI 推荐专业组数量" /></label
        ><el-button
          type="primary"
          :loading="aiBusy"
          :disabled="busy"
          @click="runAi"
          ><Sparkles :size="15" />{{
            data.ai_selection ? "重新 AI 匹配" : "开始 AI 匹配"
          }}</el-button
        >
      </div>
    </section>
    <div
      v-if="
        data.ai_selection && data.ai_selection.requested_count !== matchCount
      "
      class="notice compact"
    >
      推荐数量已调整，请重新 AI 匹配后再生成方案。
    </div>
    <div
      v-if="data.ai_selection && !failed"
      class="notice compact ai-match-result"
      role="status"
    >
      <strong>{{
        data.ai_selection.model_label
          ? "AI 精选 · " + data.ai_selection.model_label
          : "约束检查完成 · 未调用模型"
      }}</strong>
      <p>{{ data.ai_selection.message }}</p>
      <p>
        数据库 {{ data.ai_selection.catalog_universities }} 所高校 /
        {{ data.ai_selection.catalog_groups }} 个专业组 → 符合条件
        {{ data.ai_selection.eligible_count }} 个 → 精选
        {{ data.items.length }} 个专业组，覆盖
        {{ data.ai_selection.selected_universities }} 所高校。
      </p>
      <button class="text-button" :disabled="aiBusy" @click="load">
        返回候选列表
      </button>
    </div>
    <div class="rule-strip">
      <Check :size="14" />同省位次匹配<Check :size="14" />选科要求校验<Check
        :size="14"
      />招生计划校验<Check :size="14" />兴趣偏好排序
    </div>
    <div class="analysis-filters">
      <div class="risk-tabs">
        <button :class="{ active: tab === 'all' }" @click="tab = 'all'">
          {{ data.ai_selection ? "AI 精选" : "可选专业组" }}
          <span>{{ data.items.length }}</span></button
        ><button
          v-for="(label, risk) in riskLabels"
          :key="risk"
          :class="[risk, { active: tab === risk }]"
          @click="tab = risk"
        >
          <span class="status-dot"></span>{{ label }}
          <span>{{ data.counts[risk] }}</span>
        </button>
      </div>
      <div class="analysis-filter-inputs">
        <el-input
          v-model="keyword"
          clearable
          placeholder="院校 / 专业关键词"
        /><el-select v-model="region" clearable placeholder="全部地区"
          ><el-option v-for="r in regions" :key="r" :value="r" :label="r"
        /></el-select>
      </div>
    </div>
    <div class="risk-explainer">
      <Info :size="14" />按“考生位次 ÷ 近三年加权参考位次”估算：保底 ≤
      0.80；稳妥 ≤ 1.08；冲刺 ≤ 1.35。超过 1.35
      的专业组不推荐，分级不代表录取概率。
    </div>
    <div
      v-loading="busy || aiBusy"
      class="analysis-results"
      element-loading-text="正在根据已收录院校资料进行匹配…"
    >
      <div v-if="failed" class="empty-state">
        <p>
          {{
            aiFailed
              ? "AI 本次匹配未完成，请重试或返回候选列表。"
              : "匹配失败，请重试"
          }}
        </p>
        <el-button @click="aiFailed ? runAi() : load()">{{
          aiFailed ? "重试 AI 匹配" : "重新分析"
        }}</el-button
        ><el-button v-if="aiFailed" @click="load">返回候选列表</el-button>
      </div>
      <div v-else-if="filtered.length" class="school-grid">
        <SchoolCard
          v-for="group in filtered"
          :key="group.id"
          :group="group"
          @detail="show"
        />
      </div>
      <el-empty
        v-else
        description="暂无符合条件的模拟推荐，请调整画像或筛选条件"
        ><el-button @click="router.push('/profile')"
          >调整考生画像</el-button
        ></el-empty
      >
    </div></template
  ><el-empty v-else description="先完善考生画像，让我们更了解你"
    ><el-button type="primary" @click="router.push('/profile')"
      >填写我的考生画像<ArrowRight :size="15" /></el-button
  ></el-empty>
  <div class="data-disclaimer">
    <Info :size="15" />{{
      data.disclaimer ||
      "所有数据均为模拟样本。冲稳保仅为参考分级，不代表真实录取概率。"
    }}
  </div>
  <GroupDrawer v-model="drawer" :group="detail" />
</template>
<style scoped>
.ai-match-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 22px;
  margin-top: 18px;
}
.ai-match-controls h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.ai-match-controls h3 > svg {
  color: #b99768;
}
.ai-match-controls p {
  color: #8f9eb3;
  font-size: 11px;
  margin-top: 7px;
}
.ai-match-controls small {
  display: block;
  color: #a6afbd;
  font-size: 9px;
  margin-top: 5px;
}
.ai-match-actions {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
}
.ai-match-actions label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 10px;
  color: #8c9db4;
}
.ai-match-actions .el-input-number {
  width: 95px;
}
.ai-match-actions .el-button {
  height: 38px;
}
.ai-match-result {
  margin-top: 15px;
}
.ai-match-result .text-button {
  margin-top: 7px;
  font-size: 10px;
}
@media (max-width: 1250px) {
  .ai-match-controls {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .ai-match-actions {
    margin-left: auto;
  }
}
@media (max-width: 760px) {
  .ai-match-controls {
    padding: 18px;
    gap: 15px;
  }
  .ai-match-actions {
    margin-left: 0;
    width: 100%;
  }
  .ai-match-actions .el-button {
    flex: 1;
  }
}
</style>
