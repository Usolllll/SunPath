<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowUpRight,
  BookOpen,
  MapPin,
  Plus,
  Check,
  ShieldCheck,
  Heart,
  AlertTriangle,
} from "lucide-vue-next";
import type { Group } from "../api/types";
import RiskBadge from "./RiskBadge.vue";
import { number } from "../utils/format";
import { officialCheckText, safeSourceUrl } from "../utils/realdata";
import {
  cityTierLabel,
  overBudgetText,
  transferStars,
  wan,
} from "../utils/decision";
import { usePlanner } from "../stores/planner";
import { useAuth } from "../stores/auth";
import { useFavorites } from "../stores/favorites";
const props = defineProps<{ group: Group }>();
const emit = defineEmits<{
  detail: [group: Group];
  major: [name: string];
}>();
const planner = usePlanner();
const auth = useAuth();
const favorites = useFavorites();
const budget = computed(() => auth.user?.profile?.budget_total ?? null);
const costTotal = computed(() => props.group.cost?.total ?? null);
const overText = computed(() => overBudgetText(costTotal.value, budget.value));
const transfer = computed(() =>
  transferStars(props.group.university.transfer_friendly),
);
const cityTier = computed(() => props.group.university.city_tier);
const score = computed(() =>
  props.group.total_score == null ? null : props.group.total_score.toFixed(1),
);
const costYear = computed(() => props.group.cost_year ?? props.group.year);
/** 官方真实投档核对：official 为 null（如演示账号浙江）属正常缺数据，只低调提示，不报错 */
const official = computed(() => props.group.official ?? null);
const officialText = computed(() => officialCheckText(official.value));
const officialUrl = computed(() => safeSourceUrl(official.value?.source_url));
/** 收藏（真实用户行为）：本地状态由 /favorites/ids 初始化，点击乐观切换 */
const favorited = computed(() => favorites.has(props.group.university.id));
async function toggleFavorite() {
  await favorites.toggle(
    props.group.university.id,
    props.group.university.name,
  );
}
/** RTM 体检提示：只做黄/红提示，不参与筛选，也不构成报考资格认定 */
const physicalFlags = computed(() => props.group.physical_flags ?? []);
</script>
<template>
  <article class="school-card">
    <div class="school-card-top">
      <span class="school-seal" :style="{ '--seal': group.university.color }"
        ><span>{{ group.university.initials }}</span
        ><small>UNIVERSITY</small></span
      >
      <div class="school-card-flags">
        <button
          class="favorite-button"
          :class="{ active: favorited }"
          :aria-pressed="favorited"
          :aria-label="
            favorited
              ? `取消收藏${group.university.name}`
              : `收藏${group.university.name}`
          "
          :title="favorited ? '取消收藏院校' : '收藏院校'"
          @click="toggleFavorite"
        >
          <Heart :size="14" :fill="favorited ? 'currentColor' : 'none'" />
        </button>
        <span
          v-if="score"
          class="score-pill"
          title="按当前决策模式加权的综合分，仅用于同一梯度内排序"
          >综合 {{ score }}</span
        >
        <RiskBadge :risk="group.risk" />
      </div>
    </div>
    <button class="school-title" @click="emit('detail', group)">
      {{ group.university.name }}<ArrowUpRight :size="17" />
    </button>
    <div class="school-meta">
      <span><MapPin :size="12" />{{ group.university.city }}</span
      ><span>{{ group.university.category }}</span>
    </div>
    <div class="school-tags">
      <span
        v-for="tag in group.university.level.split(' / ')"
        :key="tag"
        class="tag"
        >{{ tag }}</span
      >
      <span
        v-if="cityTier != null"
        class="tag city-tag"
        title="城市分级参考城市商业魅力排行榜，仅用于排序参考"
        >{{ cityTierLabel(cityTier) }}</span
      >
      <span
        v-if="group.university.level_tier != null"
        class="tag tier-tag"
        title="院校层次分由 985 / 211 / 双一流名单换算，仅用于内部排序"
        >层次 {{ group.university.level_tier }}</span
      >
    </div>
    <p class="group-name">
      {{ group.name }} <span>{{ group.code }}</span>
    </p>
    <p class="major-line">{{ group.majors.join(" / ") }}</p>
    <div class="school-numbers">
      <div>
        <span>2025 参考位次</span
        ><strong>{{ number(group.latest_rank) }}<small> 位</small></strong>
      </div>
      <div>
        <span>2026 计划人数</span
        ><strong>{{ group.seats }}<small> 人</small></strong>
      </div>
      <div class="school-cost">
        <span>四年总成本（约）</span
        ><strong>{{ wan(costTotal) }}</strong>
      </div>
    </div>
    <div class="official-check" :class="{ missing: !official }">
      <template v-if="official">
        <span class="official-tag"><ShieldCheck :size="10" />官方核对</span>
        <span class="official-text">{{ officialText }}</span>
        <a
          v-if="officialUrl"
          class="official-link"
          :href="officialUrl"
          target="_blank"
          rel="noopener noreferrer"
          :title="`来源公告发布于 ${official.published_at || '未标注'}，真实投档线不等于录取线`"
          >来源 ↗</a
        >
        <span v-else class="official-text muted">来源链接未收录</span>
      </template>
      <template v-else>
        <span class="official-tag muted">官方数据未收录</span>
        <span class="official-text"
          >{{ group.province }}官方投档数据尚未入库，上方参考位次来自模拟样本</span
        >
      </template>
    </div>
    <div v-if="physicalFlags.length" class="physical-flags">
      <span
        v-for="flag in physicalFlags"
        :key="`${flag.level}-${flag.label}`"
        class="physical-flag"
        :class="flag.level"
        :title="`${flag.label}：${flag.text}（仅提示，不构成报考资格认定）`"
        ><AlertTriangle :size="10" /><b>{{ flag.label }}</b
        >{{ flag.text }}</span
      >
    </div>
    <div class="school-cost-row">
      <span v-if="overText" class="cost-over">{{ overText }}</span>
      <span v-else-if="budget" class="cost-ok">在家庭预算内</span>
      <span v-else class="cost-note">含学费 / 住宿费 / 生活费估算</span>
      <span :class="['school-transfer', { missing: !transfer }]">
        <span v-if="transfer" class="transfer-stars" :title="transfer.label">{{
          transfer.stars
        }}</span>
        <span>{{ transfer ? transfer.label : "转专业 未收录" }}</span>
      </span>
    </div>
    <p v-if="group.cost?.note" class="cost-support">
      成本按 {{ costYear }} 年学费 / 住宿费 + 城市等级生活费估算，非官方数据
    </p>
    <div class="school-card-bottom">
      <div class="school-card-links">
        <button class="text-button" @click="emit('detail', group)">
          查看分析 <ArrowUpRight :size="14" /></button
        ><button
          class="text-button major-card-link"
          title="查看该专业组第一个专业的介绍卡"
          @click="emit('major', group.majors[0] || group.name)"
        >
          <BookOpen :size="13" />专业卡
        </button>
      </div>
      <button
        class="add-button"
        :class="{ added: planner.items.some((x) => x.id === group.id) }"
        @click="planner.add(group)"
        :aria-label="`添加${group.university.name}到方案`"
      >
        <Check
          v-if="planner.items.some((x) => x.id === group.id)"
          :size="14"
        /><Plus v-else :size="14" />{{
          planner.items.some((x) => x.id === group.id) ? "已添加" : "加入方案"
        }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.favorite-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #f5f7fa;
  color: #9aa8bb;
  border: 1px solid #e8edf4;
  transition:
    color 0.15s,
    background 0.15s;
}
.favorite-button:hover {
  color: #d06a7a;
  background: #fff2f4;
  border-color: #f3d4da;
}
.favorite-button.active {
  color: #cf5d70;
  background: #fff0f3;
  border-color: #f0ccd4;
}
.physical-flags {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 10px;
}
.physical-flag {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 9px;
  line-height: 1.5;
  padding: 4px 7px;
  border-radius: 5px;
  overflow: hidden;
}
.physical-flag > svg {
  flex-shrink: 0;
  margin-top: 1px;
}
.physical-flag b {
  font-weight: 600;
  margin-right: 2px;
  white-space: nowrap;
}
.physical-flag.red {
  color: #b4555f;
  background: #fdf3f4;
  border: 1px solid #f6dfe2;
}
.physical-flag.yellow {
  color: #9c7a3f;
  background: #fff8ec;
  border: 1px solid #f4e6c9;
}
.official-check {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 11px;
  padding: 7px 9px;
  border: 1px solid #dfeee5;
  background: #f6faf7;
  border-radius: 6px;
  font-size: 10px;
  color: #5f7d6b;
  line-height: 1.6;
}
.official-check.missing {
  border-color: #e9eef6;
  background: #f7f9fc;
  color: #93a1b3;
}
.official-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
  font-size: 9px;
  color: #4a7f63;
  background: #e9f4ee;
  border-radius: 3px;
  padding: 1px 6px;
  white-space: nowrap;
}
.official-tag.muted {
  color: #8593a7;
  background: #eff2f7;
}
.official-text {
  flex: 1;
  min-width: 120px;
}
.official-link {
  color: #4f7fbe;
  white-space: nowrap;
  flex-shrink: 0;
}
.official-link:hover {
  color: #2f5fa3;
  text-decoration: underline;
}
</style>
