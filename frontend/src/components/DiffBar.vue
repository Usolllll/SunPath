<script setup lang="ts">
import { ArrowLeftRight, Columns2 } from "lucide-vue-next";
import type { CompareDiff } from "../api/types";
defineProps<{
  summary?: string;
  aLabel?: string;
  bLabel?: string;
  delta?: CompareDiff["metric_delta"] | null;
  loading?: boolean;
}>();
defineEmits<{ open: [] }>();
const sign = (value?: number) => {
  if (value == null) return "—";
  const text = value.toFixed(1).replace(/\.0$/, "");
  return value > 0 ? `+${text}` : text;
};
const tone = (value?: number) =>
  value == null || Math.abs(value) < 0.05 ? "flat" : value > 0 ? "up" : "down";
</script>
<template>
  <div class="diff-bar" :class="{ loading }" role="status">
    <span class="diff-bar-icon"><ArrowLeftRight :size="16" /></span>
    <div class="diff-bar-copy">
      <p>
        <strong v-if="aLabel && bLabel">{{ aLabel }} → {{ bLabel }}</strong>
        {{ summary }}
      </p>
      <div v-if="delta" class="diff-metrics">
        <span :class="['diff-metric', tone(delta.school)]"
          >院校层次 <strong>{{ sign(delta.school) }}</strong></span
        >
        <span :class="['diff-metric', tone(delta.major)]"
          >专业对口 <strong>{{ sign(delta.major) }}</strong></span
        >
        <span :class="['diff-metric', tone(delta.rank_fit)]"
          >位次适配 <strong>{{ sign(delta.rank_fit) }}</strong></span
        >
      </div>
    </div>
    <button type="button" class="diff-bar-button" @click="$emit('open')">
      <Columns2 :size="14" />并排对比
    </button>
  </div>
</template>
