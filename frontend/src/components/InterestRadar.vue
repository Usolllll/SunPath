<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as echarts from "echarts/core";
import { RadarChart } from "echarts/charts";
import { RadarComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { Compass, RotateCcw } from "lucide-vue-next";
import { RIASEC_LABELS } from "../utils/decision";
type Interests = Partial<Record<"R" | "I" | "A" | "S" | "E" | "C", number>>;
const props = defineProps<{ modelValue: Interests | null }>();
const emit = defineEmits<{ "update:modelValue": [value: Interests] }>();
echarts.use([RadarChart, RadarComponent, TooltipComponent, CanvasRenderer]);
const TYPES = ["R", "I", "A", "S", "E", "C"] as const;
const LIKERT = ["很不符合", "不太符合", "一般", "比较符合", "非常符合"];
const QUESTIONS = [
  { id: "R1", type: "R", text: "喜欢动手拆装机械、电子设备或做手工" },
  { id: "R2", type: "R", text: "比起讨论方案，更愿意直接上手操作" },
  { id: "I1", type: "I", text: "遇到问题会追问原理，并想办法验证" },
  { id: "I2", type: "I", text: "愿意长时间研究一个问题的来龙去脉" },
  { id: "A1", type: "A", text: "喜欢写作、设计、摄影等创作活动" },
  { id: "A2", type: "A", text: "对形式和美感比较敏感" },
  { id: "S1", type: "S", text: "愿意倾听他人、主动提供帮助" },
  { id: "S2", type: "S", text: "喜欢参与团队协作和集体活动" },
  { id: "E1", type: "E", text: "喜欢说服他人、推动一件事落地" },
  { id: "E2", type: "E", text: "愿意在团队里承担决策角色" },
  { id: "C1", type: "C", text: "喜欢把资料和数据整理得井井有条" },
  { id: "C2", type: "C", text: "做事偏好清晰的流程与规则" },
];
const answers = ref<Record<string, number>>({});
const expanded = ref(!props.modelValue);
const answered = computed(() => QUESTIONS.filter((q) => answers.value[q.id]).length);
const fromAnswers = computed(() => {
  if (answered.value !== QUESTIONS.length) return null;
  const result: Record<string, number> = {};
  for (const type of TYPES) {
    const values = QUESTIONS.filter((q) => q.type === type).map(
      (q) => answers.value[q.id] ?? 3,
    );
    const sum = values.reduce((total, value) => total + value, 0);
    result[type] = Math.round(((sum - values.length) / (values.length * 4)) * 100);
  }
  return result as Interests;
});
const scores = computed<Interests | null>(() => {
  if (fromAnswers.value) return fromAnswers.value;
  if (props.modelValue) return props.modelValue;
  return null;
});
const top = computed(() => {
  if (!scores.value) return [];
  return TYPES.map((type) => ({
    type,
    label: RIASEC_LABELS[type] ?? type,
    value: scores.value?.[type] ?? 0,
  }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 3);
});
watch(fromAnswers, (value) => {
  if (value) emit("update:modelValue", value);
});
const container = ref<HTMLDivElement>();
let chart: echarts.ECharts | undefined;
let observer: ResizeObserver | undefined;
function render() {
  if (!container.value || !scores.value) return;
  chart?.setOption(
    {
      textStyle: { fontFamily: "DM Sans, Microsoft YaHei, sans-serif" },
      tooltip: { trigger: "item" },
      radar: {
        indicator: TYPES.map((type) => ({
          name: `${type} ${RIASEC_LABELS[type]}`,
          max: 100,
        })),
        radius: "66%",
        splitNumber: 4,
        axisName: { color: "#77849a", fontSize: 10 },
        axisLine: { lineStyle: { color: "#e9edf3" } },
        splitLine: { lineStyle: { color: "#eef1f6" } },
        splitArea: { areaStyle: { color: ["#fbfcfe", "#f7f9fc"] } },
      },
      series: [
        {
          type: "radar",
          symbolSize: 4,
          data: [
            {
              name: "兴趣分（自评，非测评结论）",
              value: TYPES.map((type) => scores.value?.[type] ?? 0),
              areaStyle: { color: "rgba(201, 154, 95, 0.16)" },
              lineStyle: { color: "#c99a5f", width: 2 },
              itemStyle: { color: "#c99a5f" },
            },
          ],
        },
      ],
    },
    true,
  );
}
function mountChart() {
  void nextTick(() => {
    if (!container.value || !scores.value) return;
    if (!chart) {
      chart = echarts.init(container.value);
      observer = new ResizeObserver(() => chart?.resize());
      observer.observe(container.value);
    }
    render();
  });
}
watch([scores, expanded], () => {
  if (expanded.value) mountChart();
  else chart?.resize();
});
function reset() {
  answers.value = {};
}
</script>
<template>
  <section class="panel interest-panel">
    <header class="interest-head">
      <div class="interest-head-copy">
        <span class="metric-icon purple"><Compass :size="20" /></span>
        <div>
          <h3>兴趣测评 · 六型雷达</h3>
          <p>
            12 道自评题（每型 2 题，5 点李克特），结果写入画像的兴趣分，用于专业卡匹配；属于自评参考，不是能力或职业测评结论。
          </p>
        </div>
      </div>
      <div class="interest-head-actions">
        <span class="tag">已答 {{ answered }} / 12</span>
        <el-button v-if="!expanded" @click="expanded = true">开始 / 继续测评</el-button>
        <el-button v-else @click="expanded = false">收起</el-button>
      </div>
    </header>
    <div v-if="expanded" class="interest-body">
      <div class="interest-questions">
        <div v-for="question in QUESTIONS" :key="question.id" class="interest-question">
          <span class="interest-type">{{ question.type }}</span>
          <p>{{ question.text }}</p>
          <div class="likert" role="radiogroup" :aria-label="question.text">
            <button
              v-for="(label, index) in LIKERT"
              :key="label"
              type="button"
              role="radio"
              :aria-checked="answers[question.id] === index + 1"
              :class="['likert-option', { active: answers[question.id] === index + 1 }]"
              :title="label"
              @click="answers[question.id] = index + 1"
            >
              {{ index + 1 }}
            </button>
          </div>
        </div>
      </div>
      <div class="interest-result">
        <div v-if="scores" ref="container" class="interest-chart"></div>
        <el-empty v-else description="答完 12 题后生成雷达图" :image-size="70" />
        <div v-if="scores" class="interest-top">
          <span v-for="item in top" :key="item.type" class="tag warm"
            >{{ item.type }} · {{ item.label }} {{ item.value }}</span
          >
        </div>
        <div v-if="answered" class="interest-reset">
          <button type="button" class="text-button" @click="reset">
            <RotateCcw :size="13" />重新作答
          </button>
        </div>
        <p class="interest-note">
          保存画像后，兴趣分会参与「专业分量」与专业卡匹配；未作答时按专业关键词与院校类型估算。
        </p>
      </div>
    </div>
  </section>
</template>
