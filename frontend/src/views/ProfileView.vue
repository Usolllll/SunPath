<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  ArrowRight,
  Save,
  ContactRound,
  MapPin,
  Heart,
  Check,
  Target,
  Wallet,
  Stethoscope,
  Info,
  Gauge,
  Bell,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import { useAuth } from "../stores/auth";
import type { PriorityMode, Profile, ProfileCompleteness } from "../api/types";
import CoverageCard from "../components/CoverageCard.vue";
import InterestRadar from "../components/InterestRadar.vue";
import {
  MODE_HINTS,
  MODE_LABELS,
  MODE_WEIGHTS,
  MODES,
  budgetTier,
  percent,
  wan,
} from "../utils/decision";
type Interests = Partial<Record<"R" | "I" | "A" | "S" | "E" | "C", number>>;
const auth = useAuth();
const busy = ref(false);
const form = reactive<Profile>(
  auth.user?.profile
    ? JSON.parse(JSON.stringify(auth.user.profile))
    : {
        province: "浙江",
        exam_year: 2026,
        score: 600,
        rank: 30000,
        subjects: [],
        regions: [],
        majors: [],
        priority_mode: "balanced",
        budget_total: null,
        interests: null,
        physical: null,
        intent_types: null,
      },
);
const subjects = ["物理", "化学", "生物", "历史", "政治", "地理"];
const targetRegions = ref([
  "浙江",
  "上海",
  "江苏",
  "安徽",
  "湖北",
  "四川",
  "广东",
]);
// v2 决策偏好
const priorityMode = ref<PriorityMode>(form.priority_mode ?? "balanced");
const budgetWan = ref<number | undefined>(
  form.budget_total ? Math.round(form.budget_total / 1000) / 10 : undefined,
);
const physical = reactive<{
  color_weak: boolean;
  color_blind: boolean;
  naked_vision?: number;
  corrected_vision?: number;
}>({
  color_weak: form.physical?.color_weak ?? false,
  color_blind: form.physical?.color_blind ?? false,
  naked_vision: form.physical?.naked_vision ?? undefined,
  corrected_vision: form.physical?.corrected_vision ?? undefined,
});
const interests = ref<Interests>(form.interests ? { ...form.interests } : {});
const budgetYuan = computed(() => {
  if (typeof budgetWan.value !== "number" || Number.isNaN(budgetWan.value))
    return null;
  return Math.round(budgetWan.value * 10000);
});
const policy = computed(() => MODE_WEIGHTS[priorityMode.value]);
const coverageKey = computed(() =>
  JSON.stringify(auth.user?.profile?.subjects ?? []),
);
// P1：画像完整度（/ops/profile-completeness）——只展示进度与待补充项，不强制填写
const completeness = ref<ProfileCompleteness | null>(null);
const FIELD_LABELS: Record<string, string> = {
  province: "生源省份",
  exam_year: "考试年份",
  score: "高考总分",
  rank: "全省位次",
  subjects: "选考科目",
  regions: "目标地区",
  majors: "专业兴趣",
  priority_mode: "决策偏好",
  interests: "兴趣测评",
  budget_total: "家庭预算",
  physical: "体检信息",
};
const missingLabels = computed(() =>
  (completeness.value?.missing ?? []).map(
    (field) => FIELD_LABELS[field] ?? field,
  ),
);
const filledCount = computed(() => completeness.value?.filled.length ?? 0);
async function loadCompleteness() {
  if (!auth.user?.profile) return;
  try {
    completeness.value = (await api.profileCompleteness()).data;
  } catch {
    completeness.value = null;
  }
}
onMounted(async () => {
  try {
    targetRegions.value = (await api.meta()).data.regions;
  } catch {
    /* API handles error */
  }
  void loadCompleteness();
});
const complete = computed(() => form.subjects.length === 3 && form.rank > 0);
watch(priorityMode, (value) => {
  form.priority_mode = value;
});
async function save() {
  if (!complete.value)
    return ElMessage.warning("请填写有效位次并选择三门选考科目");
  busy.value = true;
  form.priority_mode = priorityMode.value;
  form.budget_total = budgetYuan.value;
  form.physical = {
    color_weak: physical.color_weak,
    color_blind: physical.color_blind,
    ...(typeof physical.naked_vision === "number"
      ? { naked_vision: physical.naked_vision }
      : {}),
    ...(typeof physical.corrected_vision === "number"
      ? { corrected_vision: physical.corrected_vision }
      : {}),
  };
  form.interests = Object.keys(interests.value).length
    ? interests.value
    : null;
  try {
    auth.user = (await api.profile(form)).data;
    ElMessage.success("考生画像已保存，推荐将按最新画像计算");
    void loadCompleteness();
  } catch {
    /* API handles error */
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">KNOW YOURSELF, FIND YOUR PATH</div>
      <h1>每条适合的路，都从了解你开始</h1>
      <p>填写你的成绩与兴趣，让推荐更贴近你的期待。</p>
    </div>
  </div>
  <div class="profile-layout">
    <form class="panel form-panel" @submit.prevent="save">
      <div class="form-section-title">
        <span class="metric-icon blue"><ContactRound :size="20" /></span>
        <div>
          <h3>我的高考信息</h3>
          <p>我们将使用同省位次进行匹配，分数仅作展示参考</p>
        </div>
      </div>
      <div class="form-grid">
        <label
          >高考省份<el-select v-model="form.province"
            ><el-option
              v-for="p in ['浙江', '江苏', '山东', '广东', '河南', '四川']"
              :key="p"
              :label="p"
              :value="p" /></el-select></label
        ><label
          >考试年份<el-select v-model="form.exam_year"
            ><el-option
              v-for="year in [2026, 2027]"
              :key="year"
              :label="`${year} 年`"
              :value="year" /></el-select></label
        ><label
          >高考总分<el-input-number
            v-model="form.score"
            :min="0"
            :max="750"
            controls-position="right"
          /><small>满分按 750 分模拟</small></label
        ><label
          >全省位次<el-input-number
            v-model="form.rank"
            :min="1"
            :max="2000000"
            controls-position="right"
          /><small>位次越小，排名越靠前</small></label
        >
      </div>
      <label class="field-label"
        >选考科目
        <span class="muted">已选 {{ form.subjects.length }} / 3</span></label
      ><el-checkbox-group
        v-model="form.subjects"
        :max="3"
        class="subject-options"
        ><el-checkbox-button v-for="s in subjects" :key="s" :value="s">{{
          s
        }}</el-checkbox-button></el-checkbox-group
      >
      <div class="form-section-title second">
        <span class="metric-icon orange"><Heart :size="20" /></span>
        <div>
          <h3>我的心之所向</h3>
          <p>偏好会影响推荐顺序，不会排除其他符合条件的院校</p>
        </div>
      </div>
      <label class="field-label">目标地区 <small>可多选</small></label
      ><el-select
        v-model="form.regions"
        multiple
        filterable
        :multiple-limit="10"
        placeholder="选择你想去的地方"
        ><el-option
          v-for="region in targetRegions"
          :key="region"
          :label="region"
          :value="region" /></el-select
      ><label class="field-label"
        >专业兴趣 <small>可多选，也可输入自定义方向</small></label
      ><el-select
        v-model="form.majors"
        multiple
        filterable
        allow-create
        default-first-option
        :multiple-limit="10"
        placeholder="选择或输入专业关键词"
        ><el-option
          v-for="major in [
            '计算机',
            '软件',
            '人工智能',
            '电子信息',
            '通信',
            '自动化',
            '经济',
            '工商管理',
            '新闻',
          ]"
          :key="major"
          :label="major"
          :value="major"
      /></el-select>
      <div class="form-section-title second">
        <span class="metric-icon purple"><Target :size="20" /></span>
        <div>
          <h3>我的决策偏好</h3>
          <p>决定推荐排序的权重：只改变同梯度内的选择与顺序，不改变候选池与冲稳保配额</p>
        </div>
      </div>
      <div class="mode-choice" role="radiogroup" aria-label="决策偏好">
        <button
          v-for="key in MODES"
          :key="key"
          type="button"
          role="radio"
          :aria-checked="priorityMode === key"
          :class="['mode-choice-item', { active: priorityMode === key }]"
          @click="priorityMode = key"
        >
          <strong>{{ MODE_LABELS[key] }}</strong>
          <small>{{ MODE_HINTS[key] }}</small>
          <span class="mode-choice-weights">
            院校 {{ percent(MODE_WEIGHTS[key].school) }} · 专业
            {{ percent(MODE_WEIGHTS[key].major) }} · 位次适配
            {{ percent(MODE_WEIGHTS[key].fit) }}
          </span>
        </button>
      </div>
      <p class="field-hint">
        当前权重：院校 {{ percent(policy.school) }} · 专业
        {{ percent(policy.major) }} · 位次适配 {{ percent(policy.fit) }}
        <span class="muted">（与智能匹配页的三档模式一致）</span>
      </p>
      <div class="form-grid budget-physical-grid">
        <label
          >家庭四年预算（万元）<el-input-number
            v-model="budgetWan"
            :min="0"
            :max="200"
            :step="1"
            controls-position="right"
            placeholder="暂不设置"
          /><small v-if="budgetYuan"
            >约 {{ wan(budgetYuan) }} · 参考分档：{{
              budgetTier(budgetYuan)
            }}；用于超预算提示，不会隐藏候选</small
          ><small v-else>不填表示暂不设置预算，仍会显示四年成本估算</small></label
        >
      </div>
      <div class="physical-block">
        <h4><Stethoscope :size="15" />体检简项（用于报考准备清单提示）</h4>
        <div class="physical-grid">
          <el-checkbox v-model="physical.color_weak">色弱</el-checkbox>
          <el-checkbox v-model="physical.color_blind">色盲</el-checkbox>
          <label
            >裸眼视力（任一眼）<el-input-number
              v-model="physical.naked_vision"
              :min="3"
              :max="5.3"
              :step="0.1"
              :precision="1"
              controls-position="right"
          /></label>
          <label
            >矫正度数（度）<el-input-number
              v-model="physical.corrected_vision"
              :min="0"
              :max="2000"
              :step="50"
              controls-position="right"
          /></label>
        </div>
        <p class="physical-hint">
          <Info :size="13" />仅用于在专业组详情里提示可能相关的《体检指导意见》条款，不构成报考资格认定；缺数据时不做推测。
        </p>
      </div>
      <div class="form-actions">
        <span><Check :size="14" />仅用于你的专属志愿规划</span
        ><el-button
          type="primary"
          native-type="submit"
          size="large"
          :loading="busy"
          ><Save :size="16" />保存考生画像</el-button
        >
      </div>
    </form>
    <aside>
      <div class="profile-preview panel">
        <span class="preview-avatar">{{ auth.user?.name.slice(0, 1) }}</span>
        <h3>{{ auth.user?.name }}</h3>
        <p>
          <MapPin :size="13" />{{ form.province }} · {{ form.exam_year }} 届考生
        </p>
        <div class="profile-preview-score">
          <div>
            <strong>{{ form.score }}</strong
            ><small>高考总分</small>
          </div>
          <div>
            <strong>{{ form.rank?.toLocaleString() }}</strong
            ><small>全省位次</small>
          </div>
        </div>
        <div class="preview-tags">
          <span v-for="s in form.subjects" :key="s" class="tag">{{ s }}</span>
        </div>
        <RouterLink to="/analysis" class="primary-button"
          >前往智能匹配<ArrowRight :size="16"
        /></RouterLink>
      </div>
      <CoverageCard :profile-key="coverageKey" />
      <RouterLink to="/messages#subscription" class="panel subscription-entry">
        <Bell :size="17" />
        <div>
          <strong>提醒订阅</strong>
          <p>征集志愿、方案提交、政策公告与数据质量提醒</p>
        </div>
        <span class="text-button">去设置</span>
      </RouterLink>
      <div v-if="completeness" class="panel completeness-card">
        <div class="completeness-head">
          <h3><Gauge :size="16" />画像完整度</h3>
          <strong>{{ completeness.score }}<small>%</small></strong>
        </div>
        <div
          class="completeness-bar"
          role="progressbar"
          :aria-valuenow="completeness.score"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`考生画像完整度 ${completeness.score}%`"
        >
          <span :style="{ width: `${Math.max(0, Math.min(100, completeness.score))}%` }"></span>
        </div>
        <p class="completeness-meta">
          已填写 {{ filledCount }} 项 · 待补充 {{ missingLabels.length }} 项
        </p>
        <p v-if="missingLabels.length" class="completeness-missing">
          待补充：{{ missingLabels.join("、") }}
        </p>
        <p v-else class="completeness-missing">
          画像信息已较完整，可随时调整；完整度只影响提示，不限制使用。
        </p>
      </div>
      <div class="notice">
        <strong>关于模拟数据</strong>
        <p>
          当前包含六省 2026 年招生计划及 2023–2025 年录取样本。选择 2027
          年时暂无招生计划，系统会明确返回空结果。
        </p>
        <p>专业组选科与数据均为演示用途，不能替代当地考试院正式规则。</p>
        <p>
          成本、城市分级、转专业友好度均为模拟 / 估算值，缺失时显示“未收录”。
        </p>
      </div>
    </aside>
  </div>
  <InterestRadar v-model="interests" />
</template>

<style scoped>
.completeness-card {
  padding: 17px 18px;
  margin-top: 16px;
}
.completeness-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.completeness-head h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: #46618a;
}
.completeness-head h3 > svg {
  color: #6c8fc6;
}
.completeness-head strong {
  font-size: 20px;
  font-weight: 550;
  color: #4a6284;
}
.completeness-head strong small {
  font-size: 10px;
  font-weight: 400;
  color: #9aa8ba;
  margin-left: 1px;
}
.completeness-bar {
  height: 6px;
  border-radius: 6px;
  background: #eef2f8;
  overflow: hidden;
  margin: 11px 0 9px;
}
.completeness-bar > span {
  display: block;
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, #6c93c9, #4f7fbe);
  transition: width 0.4s ease;
}
.completeness-meta {
  font-size: 9px;
  color: #98a4b5;
}
.completeness-missing {
  font-size: 10px;
  color: #8c9db4;
  line-height: 1.7;
  margin-top: 5px;
}
.subscription-entry {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-top: 16px;
  padding: 14px 17px;
  color: #46618a;
}
.subscription-entry > svg {
  color: #c79a5f;
  flex-shrink: 0;
}
.subscription-entry > div {
  flex: 1;
  min-width: 0;
}
.subscription-entry strong {
  font-size: 12px;
  font-weight: 500;
}
.subscription-entry p {
  font-size: 9px;
  color: #9aa8ba;
  margin-top: 3px;
}
.subscription-entry .text-button {
  font-size: 10px;
  flex-shrink: 0;
}
</style>
