<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Check, ChevronDown, ShieldAlert } from "lucide-vue-next";
import { api } from "../api";
import type { Readiness } from "../api/types";
const props = defineProps<{ groupId: number }>();
const data = ref<Readiness | null>(null);
const loading = ref(false);
const failed = ref(false);
const open = ref(false);
const issues = computed(() => [
  ...(data.value?.blockers ?? []),
  ...(data.value?.warnings ?? []),
]);
const trigger = computed(() => issues.value.length > 0);
const levelText = (level: "red" | "yellow") => (level === "red" ? "必读" : "注意");
async function load() {
  loading.value = true;
  failed.value = false;
  try {
    data.value = (await api.readiness(props.groupId)).data;
    if (trigger.value) open.value = true;
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}
watch(
  () => props.groupId,
  () => {
    data.value = null;
    open.value = false;
    void load();
  },
  { immediate: true },
);
</script>
<template>
  <section class="readiness-block">
    <button
      type="button"
      class="readiness-toggle"
      :aria-expanded="open"
      @click="open = !open"
    >
      <ShieldAlert :size="16" />
      <span>报考准备清单</span>
      <span v-if="data" class="tag subtle"
        >{{ data.blockers.length }} 项必读 · {{ data.warnings.length }} 项注意 ·
        {{ data.todos.length }} 个时间节点</span
      >
      <span v-if="trigger" class="status-dot red-dot"></span>
      <ChevronDown :size="15" :class="['readiness-chevron', { open }]" />
    </button>
    <div v-if="open" v-loading="loading" class="readiness-body">
      <template v-if="data">
        <p v-if="!issues.length" class="readiness-ok">
          <Check :size="14" />按当前体检信息，本库已收录的受限条款均未触发；这不等于
          不受限，最终以《体检指导意见》与高校招生章程为准。
        </p>
        <ul v-if="issues.length" class="readiness-list">
          <li v-for="issue in issues" :key="issue.condition + issue.label" :class="issue.level">
            <span class="readiness-level">{{ levelText(issue.level) }}</span>
            <div>
              <strong>{{ issue.label }}</strong>
              <p>{{ issue.text }}</p>
              <p v-if="issue.source" class="readiness-source">
                来源：<a
                  v-if="issue.source_url"
                  :href="issue.source_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  >{{ issue.source }}</a
                ><span v-else>{{ issue.source }}</span>
              </p>
            </div>
          </li>
        </ul>
        <h4 class="readiness-title">报名与录取时间轴（只读提示）</h4>
        <ol class="readiness-timeline">
          <li v-for="todo in data.todos" :key="todo.type" :class="{ selected: todo.selected }">
            <span class="timeline-dot"></span>
            <div>
              <strong>
                {{ todo.type }}
                <span v-if="todo.selected" class="tag warm">已关注</span>
              </strong>
              <p>{{ todo.window }}</p>
              <p class="readiness-source">
                来源：<a
                  v-if="todo.source_url"
                  :href="todo.source_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  >{{ todo.source }}</a
                ><span v-else>{{ todo.source }}</span>
              </p>
            </div>
          </li>
        </ol>
        <p class="readiness-version">
          规则版本 {{ data.version }} · {{ data.disclaimer }}
        </p>
      </template>
      <p v-else-if="failed" class="readiness-ok">
        准备清单暂不可用，请稍后重试。
      </p>
      <p v-else class="readiness-ok">正在读取准备清单…</p>
    </div>
  </section>
</template>
