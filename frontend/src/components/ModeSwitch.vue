<script setup lang="ts">
import { Building2, Check, GraduationCap, Scale, SlidersHorizontal } from "lucide-vue-next";
import type { BudgetSummary, PriorityMode, Weights } from "../api/types";
import { MODE_HINTS, MODE_LABELS, MODES, percent, wan, weightLine } from "../utils/decision";
const props = defineProps<{
  modelValue: PriorityMode;
  weights?: Weights | null;
  budget?: BudgetSummary | null;
  loading?: boolean;
}>();
defineEmits<{ "update:modelValue": [mode: PriorityMode] }>();
const MODE_ICONS = { school: Building2, balanced: Scale, major: GraduationCap };
const MODE_SHORT = { school: "院校层次优先", balanced: "院校与专业并重", major: "专业对口优先" };
const weight = (key: keyof Weights) => props.weights?.[key] ?? 0;
</script>
<template>
  <section class="panel mode-switch-panel">
    <div class="mode-switch-head">
      <div class="mode-switch-copy">
        <h3>
          <SlidersHorizontal :size="17" />取舍沙盘
          <span class="tag warm">排序 ≠ 录取</span>
          <span v-if="loading" class="tag subtle">切换中…</span>
        </h3>
        <p>
          三档模式只改变同一梯度内的选择与顺序，候选池与冲稳保配额不变；模拟数据仅供演示。
        </p>
      </div>
      <div class="mode-switch-actions"><slot name="actions" /></div>
    </div>
    <div class="mode-switch-grid" role="radiogroup" aria-label="决策模式">
      <button
        v-for="key in MODES"
        :key="key"
        type="button"
        role="radio"
        :aria-checked="modelValue === key"
        :class="['mode-option', { active: modelValue === key }]"
        :disabled="loading"
        @click="$emit('update:modelValue', key)"
      >
        <span class="mode-option-icon"
          ><component :is="MODE_ICONS[key]" :size="18" /></span
        >
        <span class="mode-option-body">
          <strong>{{ MODE_LABELS[key] }}</strong>
          <small>{{ MODE_HINTS[key] }}</small>
          <em>{{ MODE_SHORT[key] }}</em>
        </span>
        <span v-if="modelValue === key" class="mode-option-check"
          ><Check :size="14"
        /></span>
      </button>
    </div>
    <div class="mode-weights">
      <span class="mode-weights-label">当前权重</span>
      <span class="mode-weights-text">{{ weightLine(weights) }}</span>
      <div class="mode-weight-bar" aria-hidden="true">
        <i class="seg-school" :style="{ width: percent(weight('school')) }"></i>
        <i class="seg-major" :style="{ width: percent(weight('major')) }"></i>
        <i class="seg-fit" :style="{ width: percent(weight('fit')) }"></i>
      </div>
    </div>
    <div v-if="budget && budget.budget" class="mode-budget-hint">
      家庭四年预算 <strong>{{ wan(budget.budget) }}</strong> · 本次候选
      {{ budget.count }} 个专业组，其中
      <strong>{{ budget.over_budget }}</strong>
      个四年总成本超出预算（只提示，不隐藏候选）。四年成本为学费 + 住宿费 +
      城市等级生活费估算。
    </div>
  </section>
</template>
