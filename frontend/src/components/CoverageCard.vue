<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Info, Layers } from "lucide-vue-next";
import { api } from "../api";
import type { Coverage } from "../api/types";
const props = defineProps<{ profileKey: string }>();
const data = ref<Coverage | null>(null);
const loading = ref(false);
const failed = ref(false);
const gains = computed(() =>
  (data.value?.options ?? []).filter((option) => option.gain > 0),
);
async function load() {
  loading.value = true;
  failed.value = false;
  try {
    data.value = (await api.coverage()).data;
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}
watch(() => props.profileKey, load, { immediate: true });
</script>
<template>
  <section class="panel coverage-card">
    <header class="coverage-head">
      <span class="metric-icon green"><Layers :size="20" /></span>
      <div>
        <h3>选科影响卡</h3>
        <p>按本库模拟专业组统计，再加一门选科会多出多少选择。</p>
      </div>
    </header>
    <div v-loading="loading" class="coverage-body">
      <template v-if="data">
        <p class="coverage-current">
          当前选科
          <strong>{{ data.chosen.join(" + ") }}</strong>
          可报 <strong class="coverage-count">{{ data.base_groups }}</strong>
          个模拟专业组
        </p>
        <div v-if="gains.length" class="coverage-options">
          <p
            v-for="option in gains"
            :key="option.subject"
            class="coverage-option"
          >
            再选 <strong>{{ option.subject }}</strong> 可多
            <strong>{{ option.gain }}</strong> 个专业组
            <span class="muted">（合计 {{ option.groups }} 个）</span>
          </p>
        </div>
        <p v-else class="coverage-empty">
          本库中再加任意一门选考科目都不会增加可报专业组；覆盖度受模拟样本规模限制。
        </p>
        <p class="coverage-note">
          <Info :size="13" />{{ data.disclaimer }}
        </p>
      </template>
      <div v-else-if="failed" class="coverage-empty">
        选科覆盖度暂不可用，请稍后重试。
      </div>
      <p v-else class="coverage-empty">正在统计选科覆盖度…</p>
    </div>
  </section>
</template>
