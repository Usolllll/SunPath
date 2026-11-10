<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ChevronDown, Info } from "lucide-vue-next";
import type { Group, RecommendationCompare } from "../api/types";
import RiskBadge from "./RiskBadge.vue";
import { percent, wan } from "../utils/decision";
const props = defineProps<{
  compare: RecommendationCompare | null;
  loading?: boolean;
}>();
const open = defineModel<boolean>({ required: true });
const expanded = ref<string[]>([]);
watch(
  () => [open.value, props.compare] as const,
  () => {
    expanded.value = [];
  },
);
const formatScore = (value?: number | null) =>
  value == null ? "未收录" : value.toFixed(1);
const aAdded = computed(() => new Set(props.compare?.diff.added ?? []));
const aRemoved = computed(() => new Set(props.compare?.diff.removed ?? []));
const columns = computed(() => {
  if (!props.compare) return [];
  return [
    { side: "a" as const, ...props.compare.a },
    { side: "b" as const, ...props.compare.b },
  ];
});
function deltaFor(id: number): number | null {
  const value = props.compare?.diff.rank_delta?.[String(id)];
  return value == null ? null : value;
}
/** 左侧（基准）看“移出”，右侧（对照）看“新增”，共同项看位次变化 */
function statusOf(side: "a" | "b", item: Group): { text: string; tone: string } | null {
  if (side === "a" && aRemoved.value.has(item.id))
    return { text: "移出", tone: "removed" };
  if (side === "b" && aAdded.value.has(item.id))
    return { text: "新增", tone: "added" };
  const delta = deltaFor(item.id);
  if (delta == null || delta === 0) return null;
  return delta > 0
    ? { text: `下移 ${Math.abs(delta)} 位`, tone: "down" }
    : { text: `上移 ${Math.abs(delta)} 位`, tone: "up" };
}
function keyOf(side: "a" | "b", item: Group) {
  return `${side}-${item.id}`;
}
function toggle(key: string) {
  expanded.value = expanded.value.includes(key)
    ? expanded.value.filter((item) => item !== key)
    : [...expanded.value, key];
}
</script>
<template>
  <el-drawer
    v-model="open"
    title="取舍沙盘 · 并排对比"
    size="min(1120px, 96vw)"
    class="compare-drawer"
    append-to-body
  >
    <div v-if="loading" v-loading="true" class="sandbox-loading">
      正在生成两种模式的对照方案…
    </div>
    <template v-else-if="compare">
      <div class="sandbox-summary">
        <p><strong>同一候选池、同一配额</strong>，只改变梯度内的选择与顺序。</p>
        <p class="sandbox-summary-line">{{ compare.summary }}</p>
      </div>
      <div class="sandbox-grid">
        <section v-for="column in columns" :key="column.side" class="sandbox-column">
          <header class="sandbox-column-head">
            <div>
              <span class="eyebrow">{{
                column.side === "a" ? "基准方案" : "对照方案"
              }}</span>
              <h2>{{ column.label }}</h2>
            </div>
            <span class="tag subtle">{{ column.items.length }} 个志愿</span>
          </header>
          <p class="sandbox-column-weights">
            权重：院校 {{ percent(compare.weights[column.side].school) }} · 专业
            {{ percent(compare.weights[column.side].major) }} · 位次适配
            {{ percent(compare.weights[column.side].fit) }}
          </p>
          <div class="sandbox-rows">
            <article
              v-for="(item, index) in column.items"
              :key="keyOf(column.side, item)"
              :class="[
                'sandbox-row',
                {
                  expanded: expanded.includes(keyOf(column.side, item)),
                  added: column.side === 'b' && aAdded.has(item.id),
                  removed: column.side === 'a' && aRemoved.has(item.id),
                },
              ]"
            >
              <button
                type="button"
                class="sandbox-row-main"
                :aria-expanded="expanded.includes(keyOf(column.side, item))"
                @click="toggle(keyOf(column.side, item))"
              >
                <span class="sandbox-index">{{
                  String(index + 1).padStart(2, "0")
                }}</span>
                <span class="sandbox-row-info">
                  <strong>{{ item.university.name }}</strong>
                  <p>{{ item.name }} · {{ item.majors.slice(0, 2).join(" / ") }}</p>
                  <span class="sandbox-row-tags">
                    <RiskBadge :risk="item.risk" short />
                    <span class="tag">四年约 {{ wan(item.cost?.total) }}</span>
                    <span class="tag">综合分 {{ formatScore(item.total_score) }}</span>
                  </span>
                </span>
                <span
                  v-if="statusOf(column.side, item)"
                  :class="['sandbox-status', statusOf(column.side, item)!.tone]"
                  >{{ statusOf(column.side, item)!.text }}</span
                >
                <ChevronDown
                  :size="15"
                  :class="[
                    'sandbox-chevron',
                    { open: expanded.includes(keyOf(column.side, item)) },
                  ]"
                />
              </button>
              <div
                v-if="expanded.includes(keyOf(column.side, item))"
                class="sandbox-row-detail"
              >
                <div class="sandbox-scores">
                  <span
                    >院校得分<strong>{{ formatScore(item.school_score) }}</strong></span
                  >
                  <span
                    >专业得分<strong>{{ formatScore(item.major_score) }}</strong></span
                  >
                  <span
                    >位次适配<strong>{{ formatScore(item.rank_fit) }}</strong></span
                  >
                  <span
                    >转专业加分<strong>{{ formatScore(item.transfer_bonus) }}</strong></span
                  >
                  <span class="sandbox-total"
                    >综合分<strong>{{ formatScore(item.total_score) }}</strong></span
                  >
                </div>
                <ul v-if="item.reasons?.length" class="sandbox-reasons">
                  <li v-for="reason in item.reasons" :key="reason">{{ reason }}</li>
                </ul>
                <p v-if="item.warnings?.length" class="sandbox-warning">
                  {{ item.warnings.join("；") }}
                </p>
              </div>
            </article>
          </div>
          <p v-if="column.missing_tiers?.length" class="sandbox-missing">
            该方案缺少{{ column.missing_tiers.length }} 个梯度，请审慎参考。
          </p>
        </section>
      </div>
      <div class="data-disclaimer">
        <Info :size="15" />{{ compare.disclaimer }}
      </div>
    </template>
    <el-empty v-else description="暂无对比数据，请切换一次决策模式后重试" />
  </el-drawer>
</template>
