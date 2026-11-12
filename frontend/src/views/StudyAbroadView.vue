<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArrowUpRight,
  CalendarDays,
  ClipboardList,
  Compass,
  ExternalLink,
  Globe2,
  GraduationCap,
  Info,
  Languages,
  Save,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import type {
  StudyAbroadLanguageStatus,
  StudyAbroadOptions,
  StudyAbroadPathway,
  StudyAbroadPlan,
  StudyAbroadState,
  StudyAbroadTargetPayload,
} from "../api/types";
import { safeSourceUrl } from "../utils/realdata";

/** 后端未返回 options.meta.pathways 时的兜底（结构与后端契约一致，仅用于旧数据兼容） */
const PATHWAY_FALLBACK: StudyAbroadPathway[] = [
  {
    code: "gaokao",
    label: "准备或已参加高考（用高考成绩申请）",
    summary: "用高考成绩 + 语言成绩申请接受高考的院校，认可度因国家与学校而异。",
    note: "是否接受高考成绩、分数门槛与英语单科要求以学校官网当年说明为准。",
  },
  {
    code: "post_gaokao",
    label: "高考后才决定留学（预科 / 国际大一）",
    summary: "常见路径是预科（Foundation）或国际大一，用高中成绩与语言成绩申请。",
    note: "预科 / 国际大一通常有升学考核，需以官网说明为准。",
  },
  {
    code: "international",
    label: "放弃国内高考，读国际课程（A-Level / IB / AP 等）",
    summary: "以国际课程成绩申请，英国走 UCAS、美国走 Common App 或学校官网。",
    note: "国际课程体系与选课会影响可申请专业，需提前规划。",
  },
];

const options = ref<StudyAbroadOptions | null>(null);
const state = ref<StudyAbroadState | null>(null);
const loading = ref(false);
const failed = ref(false);
const saving = ref(false);
const clearing = ref(false);
// 表单（与后端契约字段对应）
const regionCode = ref("");
const schoolId = ref("");
const testType = ref("");
const score = ref<number | undefined>(undefined);
const major = ref("");
const formError = ref("");
// M11 增量：升学路径与高考成绩
const path = ref("gaokao");
const gaokaoScore = ref<number | undefined>(undefined);
// 准备清单仅本地状态，不上传、不持久化
const checked = ref<Record<string, boolean>>({});

const regions = computed(() => options.value?.regions ?? []);
const tests = computed(() => options.value?.tests ?? []);
const pathways = computed<StudyAbroadPathway[]>(
  () => options.value?.meta?.pathways ?? PATHWAY_FALLBACK,
);
const currentPathway = computed(
  () => pathways.value.find((item) => item.code === path.value) ?? null,
);
const currentRegion = computed(
  () => regions.value.find((region) => region.code === regionCode.value) ?? null,
);
const schools = computed(() => currentRegion.value?.schools ?? []);
const currentSchool = computed(
  () => schools.value.find((school) => school.id === schoolId.value) ?? null,
);
const currentTest = computed(
  () => tests.value.find((item) => item.code === testType.value) ?? null,
);
const maxScore = computed(() => (testType.value === "toefl" ? 120 : 9));
const scoreHint = computed(
  () =>
    currentTest.value?.scale ??
    (testType.value === "toefl" ? "0–120 分" : "0–9 分"),
);
const scoreOutOfRange = computed(
  () =>
    typeof score.value === "number" &&
    (score.value < 0 || score.value > maxScore.value),
);
const majorSuggestions = computed(() => currentSchool.value?.majors ?? []);
const target = computed(() => state.value?.target ?? null);
const plan = computed<StudyAbroadPlan | null>(() => state.value?.plan ?? null);
const disclaimer = computed(
  () =>
    state.value?.disclaimer ||
    options.value?.disclaimer ||
    "申请要求与截止日期以学校官网为准，本模块只做官方入口索引，不代填申请表。",
);
const schoolTotal = computed(() =>
  regions.value.reduce((total, region) => total + region.schools.length, 0),
);
const checklistDone = computed(
  () =>
    plan.value?.checklist.filter((item) => checked.value[item.key]).length ?? 0,
);
// 官方链接统一过滤，只允许 http(s)，并在新窗口打开
const safeLinks = computed(() =>
  (plan.value?.links ?? [])
    .map((link) => ({ label: link.label, href: safeSourceUrl(link.url) }))
    .filter((link): link is { label: string; href: string } => !!link.href),
);
const schoolHref = computed(() =>
  safeSourceUrl(plan.value?.school.official_url ?? ""),
);
const STATUS_META: Record<
  StudyAbroadLanguageStatus,
  { tone: string; badge: string; detail: string }
> = {
  reached: { tone: "reached", badge: "达到", detail: "达到参考最低语言要求" },
  below: { tone: "below", badge: "低于", detail: "低于参考最低语言要求" },
  unknown: {
    tone: "unknown",
    badge: "暂无参考",
    detail: "暂无参考语言要求，请查官网",
  },
};
const langMeta = computed(
  () => STATUS_META[plan.value?.language.status ?? "unknown"],
);
const gaokaoScoreInvalid = computed(
  () =>
    typeof gaokaoScore.value === "number" &&
    (!Number.isInteger(gaokaoScore.value) ||
      gaokaoScore.value < 0 ||
      gaokaoScore.value > 750),
);
const planPathway = computed(() => plan.value?.pathway ?? null);
const planGaokao = computed(() => plan.value?.gaokao ?? null);
const showGaokaoCard = computed(() => planPathway.value?.code === "gaokao");
const gaokaoTone = computed(() => {
  const accepted = planGaokao.value?.accepted;
  if (accepted === true) return "accepted";
  if (accepted === false) return "not-accepted";
  return "unknown";
});
const gaokaoLabel = computed(() => {
  const check = planGaokao.value;
  if (!check) return "未标注";
  if (check.label) return check.label;
  if (check.accepted === true) return "接受";
  if (check.accepted === false) return "通常不接受";
  return "未标注";
});
const pathWarning = computed(() => (plan.value?.path_warning ?? "").trim());
const schoolQualifications = computed(
  () => plan.value?.school.qualifications ?? [],
);

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
function applyState(data: StudyAbroadState) {
  state.value = data;
  checked.value = {};
  const saved = data.target;
  regionCode.value = saved?.region ?? regions.value[0]?.code ?? "";
  testType.value = saved?.test_type ?? tests.value[0]?.code ?? "";
  schoolId.value = saved?.school_id ?? "";
  score.value = typeof saved?.test_score === "number" ? saved.test_score : undefined;
  major.value = saved?.target_major ?? "";
  path.value = saved?.path ?? "gaokao";
  gaokaoScore.value =
    typeof saved?.gaokao_score === "number" ? saved.gaokao_score : undefined;
  formError.value = "";
}
async function load() {
  loading.value = true;
  failed.value = false;
  try {
    const [optionResponse, stateResponse] = await Promise.all([
      api.studyAbroadOptions(),
      api.studyAbroadTarget(),
    ]);
    options.value = optionResponse.data;
    applyState(stateResponse.data);
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}
function onRegionChange() {
  // 地区联动：切换地区后清空学校与建议专业
  schoolId.value = "";
  formError.value = "";
}
function onPathChange() {
  // 非高考路径不展示、也不提交高考成绩
  if (path.value !== "gaokao") gaokaoScore.value = undefined;
  formError.value = "";
}
function fillMajor(name: string) {
  major.value = name;
  formError.value = "";
}
function toggleCheck(key: string, value: unknown) {
  checked.value[key] = Boolean(value);
}
function validate(): string | null {
  if (!currentRegion.value) return "请选择目标地区";
  if (!currentSchool.value) return "请先选择目标学校";
  if (!currentPathway.value) return "请选择你的升学路径";
  if (!currentTest.value) return "请选择考试类型";
  if (score.value == null || Number.isNaN(score.value))
    return `请填写${currentTest.value.label}成绩`;
  if (score.value < 0 || score.value > maxScore.value)
    return `${currentTest.value.label} 成绩应在 0–${maxScore.value} 之间，请检查后重试`;
  if (path.value === "gaokao" && gaokaoScoreInvalid.value)
    return "高考成绩应为 0–750 的整数（可不填）";
  if (major.value.trim().length > 60) return "目标专业请控制在 60 个字以内";
  return null;
}
async function save() {
  if (saving.value) return;
  const problem = validate();
  if (problem) {
    formError.value = problem;
    ElMessage.warning(problem);
    return;
  }
  formError.value = "";
  saving.value = true;
  try {
    const payload: StudyAbroadTargetPayload = {
      region: regionCode.value,
      school_id: schoolId.value,
      test_type: testType.value,
      test_score: Number(score.value),
      path: path.value,
    };
    const text = major.value.trim();
    if (text) payload.target_major = text;
    if (path.value === "gaokao" && typeof gaokaoScore.value === "number")
      payload.gaokao_score = Math.round(gaokaoScore.value);
    const { data } = await api.saveStudyAbroadTarget(payload);
    applyState(data);
    ElMessage.success("留学目标已保存");
  } catch {
    /* 错误提示由 axios 拦截器统一展示 */
  } finally {
    saving.value = false;
  }
}
async function clear() {
  if (clearing.value || !target.value) return;
  clearing.value = true;
  try {
    await api.clearStudyAbroadTarget();
    state.value = { target: null, plan: null, disclaimer: disclaimer.value };
    checked.value = {};
    schoolId.value = "";
    score.value = undefined;
    gaokaoScore.value = undefined;
    major.value = "";
    formError.value = "";
    ElMessage.success("已清除留学目标");
  } catch {
    /* 错误提示由 axios 拦截器统一展示 */
  } finally {
    clearing.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">STUDY ABROAD · GO FURTHER</div>
      <h1>你想去留学吗？来这里吧</h1>
      <p>
        选地区、看语言要求、直达学校官方申请入口；本模块只做官方入口索引，不代填申请表。
      </p>
    </div>
    <span v-if="options" class="study-pill"
      ><Globe2 :size="14" />{{ regions.length }} 个地区 ·
      {{ schoolTotal }} 所院校索引</span
    >
  </div>

  <div
    v-loading="loading"
    class="study-layout"
    element-loading-text="正在读取留学模块索引…"
  >
    <div v-if="failed" class="empty-state">
      <p>留学规划数据暂不可用，请确认后端 /api/study-abroad 已就绪后重试。</p>
      <el-button @click="load">重新加载</el-button>
    </div>
    <template v-else-if="options">
      <div class="study-main">
        <section class="panel study-form-panel">
          <div class="section-heading">
            <div>
              <h2 class="study-section-title">
                <GraduationCap :size="18" />我的留学目标
              </h2>
              <p>填写地区、学校与语言成绩，保存后可查看语言要求对比与官方入口。</p>
            </div>
            <span v-if="target" class="tag warm">已保存</span>
          </div>
          <div class="study-form-grid">
            <label class="study-field"
              >目标地区
              <el-select
                v-model="regionCode"
                placeholder="选择目标地区"
                @change="onRegionChange"
                ><el-option
                  v-for="region in regions"
                  :key="region.code"
                  :value="region.code"
                  :label="`${region.label} · ${region.schools.length} 所院校`"
              /></el-select>
              <small>{{
                currentRegion?.application_portal || "选择地区后显示申请平台"
              }}</small>
            </label>
            <label class="study-field"
              >目标学校
              <el-select
                v-model="schoolId"
                filterable
                :disabled="!schools.length"
                placeholder="先选择地区，再选择学校"
                ><el-option
                  v-for="school in schools"
                  :key="school.id"
                  :value="school.id"
                  :label="
                    school.name_zh
                      ? `${school.name_zh} · ${school.name}`
                      : school.name
                  "
              /></el-select>
              <small v-if="currentSchool"
                >{{ currentSchool.name }} · 入学时间
                {{ currentSchool.intakes.join("、") || "以官网为准" }}</small
              >
              <small v-else>学校列表随目标地区联动</small>
            </label>
            <label class="study-field"
              >考试类型
              <el-select v-model="testType" placeholder="选择考试类型"
                ><el-option
                  v-for="test in tests"
                  :key="test.code"
                  :value="test.code"
                  :label="test.label" /></el-select>
              <small>{{ currentTest?.scale || "选择考试后显示量程" }}</small>
            </label>
            <label class="study-field"
              >我的成绩
              <el-input-number
                v-model="score"
                :min="0"
                :max="maxScore"
                :step="0.5"
                :precision="1"
                controls-position="right"
                :placeholder="`${scoreHint}`"
              />
              <small :class="{ 'field-warning': scoreOutOfRange }"
                >范围 {{ scoreHint }}，步长 0.5{{
                  scoreOutOfRange ? "；当前分数超出量程" : ""
                }}</small
              >
            </label>
          </div>
          <div class="study-path-block">
            <label class="study-field"
              >你的升学路径
              <el-select
                v-model="path"
                placeholder="选择升学路径"
                @change="onPathChange"
                ><el-option
                  v-for="item in pathways"
                  :key="item.code"
                  :value="item.code"
                  :label="item.label" /></el-select>
              <small v-if="currentPathway">{{ currentPathway.summary }}</small>
              <small v-if="currentPathway" class="study-path-note">{{
                currentPathway.note
              }}</small>
            </label>
            <label v-if="path === 'gaokao'" class="study-field"
              >高考成绩（0–750，可选）
              <el-input-number
                v-model="gaokaoScore"
                :min="0"
                :max="750"
                :step="1"
                :precision="0"
                controls-position="right"
                placeholder="可不填"
              />
              <small :class="{ 'field-warning': gaokaoScoreInvalid }"
                >仅用于结果区「高考成绩认可参考」提示，不填也可保存{{
                  gaokaoScoreInvalid ? "；成绩应为 0–750 的整数" : ""
                }}</small
              >
            </label>
          </div>
          <label class="study-field study-major-field"
            >目标专业
            <el-input
              v-model="major"
              maxlength="60"
              show-word-limit
              placeholder="例如：计算机科学（可留空）"
          /></label>
          <div v-if="majorSuggestions.length" class="major-suggest">
            <span class="major-suggest-label"
              >{{ currentSchool?.name_zh }} 可选专业</span
            >
            <button
              v-for="name in majorSuggestions"
              :key="name"
              type="button"
              :class="['major-suggest-chip', { active: major === name }]"
              @click="fillMajor(name)"
            >
              {{ name }}
            </button>
          </div>
          <p v-if="formError" class="form-error" role="alert">
            {{ formError }}
          </p>
          <div class="study-form-actions">
            <el-button type="primary" size="large" :loading="saving" @click="save"
              ><Save :size="16" />保存留学目标</el-button
            ><el-button
              size="large"
              :loading="clearing"
              :disabled="!target"
              @click="clear"
              >清除</el-button
            ><span v-if="target" class="study-saved-at"
              >上次保存：{{ target.saved_at }} · {{ target.path_label }}</span
            >
          </div>
        </section>
        <aside class="study-aside">
          <section class="panel study-hint-panel">
            <h3><Info :size="16" />语言成绩与申请提示</h3>
            <p v-if="options.meta.language_hint">
              {{ options.meta.language_hint }}
            </p>
            <p v-if="options.meta.note">{{ options.meta.note }}</p>
            <p v-if="options.meta.updated_at" class="study-aside-meta">
              索引更新时间：{{ options.meta.updated_at }} ·
              {{ options.meta.data_mode || "参考索引" }}
            </p>
            <p class="study-aside-foot">{{ options.disclaimer }}</p>
          </section>
        </aside>
      </div>

      <section v-if="plan" class="study-results">
        <div v-if="pathWarning" class="path-warning" role="status">
          <Info :size="15" /><span>{{ pathWarning }}</span>
        </div>
        <section class="panel study-result-card pathway-card">
          <div class="study-result-head">
            <h3><Compass :size="16" />升学路径</h3>
            <span class="tag warm">{{ plan.pathway.label }}</span>
          </div>
          <p class="pathway-summary">{{ plan.pathway.summary }}</p>
          <p v-if="plan.pathway.region_note" class="pathway-region-note">
            <Globe2 :size="13" /><span
              ><strong>{{ target?.region_label || "目标地区" }}：</strong
              >{{ plan.pathway.region_note }}</span
            >
          </p>
          <p v-if="plan.pathway.note" class="language-note">
            {{ plan.pathway.note }}
          </p>
          <div v-if="schoolQualifications.length" class="pathway-qualifications">
            <span class="pathway-qualifications-label">常见申请资格</span>
            <span v-for="item in schoolQualifications" :key="item" class="tag">{{
              item
            }}</span>
          </div>
        </section>
        <section v-if="showGaokaoCard" class="panel study-result-card gaokao-card">
          <div class="study-result-head">
            <h3><GraduationCap :size="16" />高考成绩认可参考</h3>
            <span :class="['gaokao-badge', gaokaoTone]">{{ gaokaoLabel }}</span>
          </div>
          <p class="pathway-summary">
            {{ plan.gaokao?.note || "该院校是否接受高考成绩未标注，请查看学校官网。" }}
          </p>
          <p v-if="target?.gaokao_score != null" class="gaokao-score-line">
            你填写的高考成绩：<strong>{{ target.gaokao_score }}</strong> 分
          </p>
          <p class="language-note">
            高考成绩认可情况仅为参考，是否接受与分数门槛以学校官网当年说明为准。
          </p>
        </section>
        <section class="panel study-result-card language-card">
          <div class="study-result-head">
            <h3><Languages :size="16" />语言要求对比</h3>
            <span class="tag">{{ target?.region_label || plan.school.name_zh }}</span>
          </div>
          <p class="study-school-line">
            <strong>{{ plan.school.name_zh }}</strong>
            <span>{{ plan.school.name }}</span>
            <a
              v-if="schoolHref"
              :href="schoolHref"
              target="_blank"
              rel="noopener noreferrer"
              >学校官网 <ArrowUpRight :size="12"
            /></a>
          </p>
          <div class="language-compare">
            <div class="language-cell">
              <span>你的成绩</span
              ><strong>{{ plan.language.user_score }}</strong
              ><small>{{ plan.language.test_label }}</small>
            </div>
            <div class="language-divider" aria-hidden="true">vs</div>
            <div class="language-cell">
              <span>参考最低要求</span
              ><strong>{{
                plan.language.required == null
                  ? "未收录"
                  : plan.language.required
              }}</strong
              ><small>{{ plan.language.scale }}</small>
            </div>
            <div :class="['language-status', langMeta.tone]">
              <span class="status-dot"></span>{{ langMeta.badge }}
            </div>
          </div>
          <p :class="['language-label', langMeta.tone]">
            {{ langMeta.detail }}
            <span v-if="plan.language.label && plan.language.label !== langMeta.detail"
              >· {{ plan.language.label }}</span
            >
          </p>
          <p class="language-note">
            参考值，具体以官网为准；语言成绩有效期与单项分要求请查看学校官网。
          </p>
        </section>

        <section class="panel study-result-card">
          <div class="study-result-head">
            <h3><ExternalLink :size="16" />官方申请入口</h3>
            <span class="tag subtle">{{ safeLinks.length }} 个入口</span>
          </div>
          <div v-if="safeLinks.length" class="study-links">
            <a
              v-for="link in safeLinks"
              :key="link.label + link.href"
              class="study-link"
              :href="link.href"
              target="_blank"
              rel="noopener noreferrer"
              ><span class="study-link-label"
                >{{ link.label }}<em>{{ domainOf(link.href) }}</em></span
              ><ArrowUpRight :size="15" /></a
            >
          </div>
          <el-empty v-else description="暂无可用官方入口" :image-size="60" />
          <p class="language-note">
            全部链接在新窗口打开；本模块不嵌入第三方页面、不代填申请表，请核对域名后访问官网。
          </p>
        </section>

        <section class="panel study-result-card">
          <div class="study-result-head">
            <h3><ClipboardList :size="16" />申请准备清单</h3>
            <span class="tag"
              >{{ checklistDone }} / {{ plan.checklist.length }} 已准备</span
            >
          </div>
          <el-checkbox
            v-for="item in plan.checklist"
            :key="item.key"
            class="checklist-item"
            :model-value="!!checked[item.key]"
            @change="toggleCheck(item.key, $event)"
            ><span class="checklist-label">{{ item.label }}</span
            ><small class="checklist-detail">{{ item.detail }}</small></el-checkbox
          >
          <p class="language-note">
            勾选仅在当前页面保存，不会上传；材料要求以学校官网最新说明为准。
          </p>
        </section>

        <section class="panel study-result-card">
          <div class="study-result-head">
            <h3><CalendarDays :size="16" />申请时间线</h3>
            <span class="tag subtle">通用规划节点</span>
          </div>
          <ol class="study-timeline">
            <li v-for="(node, index) in plan.timeline" :key="node.stage">
              <span class="timeline-index">{{
                String(index + 1).padStart(2, "0")
              }}</span>
              <div>
                <strong
                  >{{ node.stage
                  }}<span v-if="node.when" class="tag">{{ node.when }}</span></strong
                >
                <p>{{ node.detail }}</p>
              </div>
            </li>
          </ol>
          <p class="language-note">
            具体截止日期每年可能变化，请以学校官网与申请平台为准；本页不提供逐校截止日期。
          </p>
        </section>

        <section class="study-result-card study-plan-note">
          <Info :size="14" /><span
            >{{ disclaimer }}
            语言要求为参考值；学校入学时间
            {{ plan.school.intakes?.join("、") || "以官网为准" }}。</span
          >
        </section>
      </section>

      <section v-else class="panel study-empty">
        <div class="study-empty-icon"><Globe2 :size="26" /></div>
        <h3>先保存一个留学目标</h3>
        <p>
          填写目标地区与学校并保存后，这里会显示语言要求三态对比、官方申请入口、申请准备清单与时间线。
        </p>
      </section>
    </template>
  </div>

  <div v-if="options" class="data-disclaimer">
    <Info :size="15" />{{ disclaimer }}
  </div>
</template>

<style scoped>
.study-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 10px;
  color: #74869f;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px 13px;
  white-space: nowrap;
}
.study-pill > svg {
  color: #6b8fc4;
}
.study-layout {
  min-height: 260px;
}
.study-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 22px;
  align-items: start;
}
.study-form-panel {
  padding: 23px 25px 21px;
}
.study-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  color: #354d6e;
}
.study-section-title > svg {
  color: #b99768;
}
.study-form-panel .section-heading p {
  font-size: 10px;
  color: #96a2b4;
  margin-top: 5px;
  line-height: 1.8;
  max-width: 560px;
}
.study-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 22px;
  margin-top: 19px;
}
.study-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: #697b94;
  min-width: 0;
}
.study-field > small {
  font-size: 10px;
  color: #a0adbc;
  line-height: 1.7;
}
.study-field .el-input-number {
  width: 100%;
}
.study-field small.field-warning {
  color: #c08a4e;
}
.study-major-field {
  margin-top: 18px;
}
.major-suggest {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 11px;
}
.major-suggest-label {
  font-size: 10px;
  color: #98a4b5;
  margin-right: 2px;
}
.major-suggest-chip {
  font-size: 10px;
  color: #6d7f98;
  background: #f2f6fb;
  border: 1px solid #e6edf6;
  border-radius: 20px;
  padding: 5px 12px;
  transition:
    color 0.15s,
    background 0.15s,
    border-color 0.15s;
}
.major-suggest-chip:hover {
  color: #3f6aa6;
  background: #eaf2fd;
  border-color: #cfdff2;
}
.major-suggest-chip.active {
  color: #fff;
  background: #4f7fbe;
  border-color: #4f7fbe;
}
.form-error {
  margin-top: 13px;
  font-size: 11px;
  color: #c07262;
  background: #fdf3f1;
  border: 1px solid #f4e2de;
  border-radius: 6px;
  padding: 8px 11px;
  line-height: 1.7;
}
.study-form-actions {
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
.study-form-actions .el-button {
  margin: 0;
}
.study-saved-at {
  font-size: 9px;
  color: #a4b0c0;
  margin-left: auto;
}
.study-aside {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.study-hint-panel {
  padding: 20px 21px;
}
.study-hint-panel h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #3e5678;
}
.study-hint-panel h3 > svg {
  color: #b99768;
}
.study-hint-panel p {
  font-size: 10px;
  color: #8b9bb1;
  line-height: 1.95;
  margin-top: 10px;
}
.study-hint-panel .study-aside-meta {
  font-size: 9px;
  color: #a4b0c0;
  border-top: 1px dashed #e8eef6;
  padding-top: 10px;
}
.study-aside-foot {
  font-size: 9px !important;
  color: #a09a8c !important;
  background: #fbf8f2;
  border-radius: 6px;
  padding: 9px 11px;
}
.study-results {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 20px;
}
.study-result-card {
  padding: 19px 21px 17px;
  min-width: 0;
}
.language-card {
  grid-column: 1 / -1;
}
.study-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 13px;
}
.study-result-head h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #3e5678;
}
.study-result-head h3 > svg {
  color: #b99768;
}
.study-school-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #8b9bb1;
}
.study-school-line strong {
  font-size: 14px;
  font-weight: 600;
  color: #334a6a;
}
.study-school-line a {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: #4f7fbe;
  margin-left: auto;
}
.study-school-line a:hover {
  text-decoration: underline;
}
.language-compare {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 15px;
  background: #fafcff;
  border: 1px solid #edf2f9;
  border-radius: 9px;
  padding: 15px 18px;
}
.language-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 110px;
}
.language-cell > span {
  font-size: 9px;
  color: #98a5b8;
}
.language-cell > strong {
  font-size: 24px;
  font-weight: 550;
  color: #3e5676;
  letter-spacing: -0.5px;
}
.language-cell > small {
  font-size: 9px;
  color: #a4b0c0;
}
.language-divider {
  font-size: 10px;
  color: #b9c4d2;
  letter-spacing: 1px;
}
.language-status {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 6px 12px;
  border-radius: 20px;
  white-space: nowrap;
}
.language-status.reached {
  color: #5d927c;
  background: #edf6f1;
}
.language-status.below {
  color: #c08a4e;
  background: #fff5e9;
}
.language-status.unknown {
  color: #8b9bb1;
  background: #f2f5f9;
}
.language-label {
  margin-top: 12px;
  font-size: 11px;
  line-height: 1.8;
}
.language-label.reached {
  color: #5d927c;
}
.language-label.below {
  color: #b07a48;
}
.language-label.unknown {
  color: #8b9bb1;
}
.language-note {
  margin-top: 10px;
  font-size: 9px;
  color: #a6b2c2;
  line-height: 1.9;
}
.study-links {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.study-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #f7faff;
  border: 1px solid #e4edf8;
  border-radius: 8px;
  padding: 11px 14px;
  color: #45628a;
  transition:
    background 0.15s,
    border-color 0.15s;
}
.study-link:hover {
  background: #eef5ff;
  border-color: #c9dcf2;
}
.study-link-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: #3f5678;
}
.study-link-label em {
  font-style: normal;
  font-size: 9px;
  color: #93a4ba;
}
.study-link > svg {
  color: #7d9dc4;
  flex-shrink: 0;
}
.checklist-item {
  display: flex;
  align-items: flex-start;
  width: 100%;
  margin: 0 0 9px;
  white-space: normal;
}
.checklist-item :deep(.el-checkbox__label) {
  display: flex;
  flex-direction: column;
  gap: 2px;
  white-space: normal;
  line-height: 1.6;
}
.checklist-label {
  font-size: 12px;
  color: #4d6485;
}
.checklist-detail {
  font-size: 9px;
  color: #9aa8ba;
  line-height: 1.8;
}
.study-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.study-timeline > li {
  display: flex;
  gap: 12px;
  position: relative;
  padding: 9px 0;
}
.study-timeline > li + li:before {
  content: "";
  position: absolute;
  left: 12px;
  top: -6px;
  height: 12px;
  border-left: 1px dashed #dbe4ef;
}
.timeline-index {
  width: 25px;
  height: 25px;
  border-radius: 50%;
  background: #f1f5fb;
  border: 1px solid #e4ebf5;
  color: #8397b2;
  font-size: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}
.study-timeline strong {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  color: #4d6485;
}
.study-timeline strong .tag {
  font-size: 8px;
}
.study-timeline p {
  font-size: 10px;
  color: #93a1b4;
  line-height: 1.85;
  margin-top: 4px;
}
.study-plan-note {
  grid-column: 1 / -1;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid #f0e1ca;
  background: #fffaf2;
  border-radius: 9px;
  padding: 14px 17px;
  font-size: 10px;
  color: #9a805a;
  line-height: 1.9;
}
.study-plan-note > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.study-empty {
  margin-top: 20px;
  padding: 46px 24px;
  text-align: center;
}
.study-empty-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: #eef4fc;
  color: #6b8fc4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.study-empty h3 {
  font-size: 15px;
  color: #3f5678;
  margin-top: 13px;
}
.study-empty p {
  font-size: 11px;
  color: #96a2b4;
  line-height: 1.9;
  max-width: 520px;
  margin: 8px auto 0;
}
.study-path-block {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 18px 22px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed #e9eef6;
}
.study-field small.study-path-note {
  color: #a09a8c;
  background: #fbf8f2;
  border-radius: 5px;
  padding: 6px 9px;
  line-height: 1.8;
}
.path-warning {
  grid-column: 1 / -1;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fff7ed;
  border: 1px solid #f3ddba;
  border-radius: 8px;
  padding: 12px 15px;
  font-size: 11px;
  color: #a9732f;
  line-height: 1.85;
}
.path-warning > svg {
  flex-shrink: 0;
  margin-top: 1px;
  color: #c08a4e;
}
.pathway-card,
.gaokao-card {
  grid-column: 1 / -1;
}
.pathway-summary {
  font-size: 12px;
  color: #5f7390;
  line-height: 1.9;
}
.pathway-region-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 11px;
  background: #f7faff;
  border: 1px solid #e6eef9;
  border-radius: 7px;
  padding: 11px 13px;
  font-size: 11px;
  color: #6e829d;
  line-height: 1.9;
}
.pathway-region-note > svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: #7d9dc4;
}
.pathway-region-note strong {
  color: #4f6c92;
  font-weight: 600;
}
.pathway-qualifications {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 12px;
}
.pathway-qualifications-label {
  font-size: 10px;
  color: #98a4b5;
}
.gaokao-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  padding: 5px 11px;
  border-radius: 20px;
  white-space: nowrap;
}
.gaokao-badge.accepted {
  color: #5d927c;
  background: #edf6f1;
}
.gaokao-badge.not-accepted {
  color: #c08a4e;
  background: #fff5e9;
}
.gaokao-badge.unknown {
  color: #8b9bb1;
  background: #f2f5f9;
}
.gaokao-score-line {
  margin-top: 10px;
  font-size: 11px;
  color: #7d8ea6;
}
.gaokao-score-line strong {
  font-size: 16px;
  font-weight: 600;
  color: #3e5676;
  margin: 0 2px;
}
@media (max-width: 1250px) {
  .study-main {
    grid-template-columns: minmax(0, 1fr) 260px;
    gap: 16px;
  }
  .study-results {
    gap: 14px;
  }
}
@media (max-width: 1020px) {
  .study-main {
    grid-template-columns: 1fr;
  }
  .study-results {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 760px) {
  .study-form-panel {
    padding: 19px;
  }
  .study-form-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .language-compare {
    gap: 12px;
    padding: 13px;
  }
  .language-status {
    margin-left: 0;
  }
  .study-pill {
    display: none;
  }
}
</style>
