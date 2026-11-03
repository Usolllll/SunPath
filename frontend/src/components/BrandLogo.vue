<script setup lang="ts">
defineProps<{ compact?: boolean }>();
</script>
<template>
  <div class="brand">
    <span class="brand-icon"
      ><svg viewBox="0 0 40 40" fill="none">
        <path
          d="M8 25a12 12 0 0 1 24 0"
          stroke="currentColor"
          stroke-width="2.5"
        />
        <path
          d="M20 3v5M6 10l4 4M34 10l-4 4M3 25h5M32 25h5"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
        />
        <path
          d="M8 31h24M13 36h14"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
        /></svg></span
    ><span v-if="!compact"
      ><strong>SunPath<span class="brand-dot">.</span></strong
      ><small>阳光志愿 · 向未来出发</small></span
    >
  </div>
</template>
