<script setup lang="ts">
import type { Risk } from "../api/types";
import { riskLabels } from "../utils/format";
defineProps<{ risk?: Risk; short?: boolean }>();
</script>
<template>
  <span v-if="risk" :class="['risk-badge', risk]"
    ><span class="status-dot"></span
    >{{ short ? riskLabels[risk].slice(0, 1) : riskLabels[risk] }}</span
  ><span v-else class="tag">待匹配</span>
</template>
