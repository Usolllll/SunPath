<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArrowRight,
  Sparkles,
  SlidersHorizontal,
  Check,
  Info,
  RefreshCw,
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
  if (!auth.user?.profile) return;
  busy.value = true;
  failed.value = false;
  try {
    data.value = (await api.recommendations()).data;
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
async function generate() {
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
    const response = (await api.generate()).data;
    if (!response.items.length)
      return ElMessage.warning(
        "当前画像暂无可用候选，请调整画像或浏览招生数据",
      );
    planner.replace(response.items);
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
      :disabled="!data.items.length"
      @click="generate"
      ><Sparkles :size="17" />一键生成志愿方案</el-button
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
    <div class="rule-strip">
      <Check :size="14" />同省位次匹配<Check :size="14" />选科要求校验<Check
        :size="14"
      />招生计划校验<Check :size="14" />兴趣偏好排序<button
        class="text-button"
        @click="load"
      >
        <RefreshCw :size="14" />重新分析
      </button>
    </div>
    <div class="analysis-filters">
      <div class="risk-tabs">
        <button :class="{ active: tab === 'all' }" @click="tab = 'all'">
          全部匹配 <span>{{ data.items.length }}</span></button
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
    <div v-loading="busy" class="analysis-results">
      <div v-if="failed" class="empty-state">
        <p>匹配失败，请重试</p>
        <el-button @click="load">重新分析</el-button>
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
