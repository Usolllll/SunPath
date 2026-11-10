<script setup lang="ts">
import { computed } from "vue";
import { ArrowUpRight, BookOpen, MapPin, Plus, Check } from "lucide-vue-next";
import type { Group } from "../api/types";
import RiskBadge from "./RiskBadge.vue";
import { number } from "../utils/format";
import {
  cityTierLabel,
  overBudgetText,
  transferStars,
  wan,
} from "../utils/decision";
import { usePlanner } from "../stores/planner";
import { useAuth } from "../stores/auth";
const props = defineProps<{ group: Group }>();
const emit = defineEmits<{
  detail: [group: Group];
  major: [name: string];
}>();
const planner = usePlanner();
const auth = useAuth();
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
</script>
<template>
  <article class="school-card">
    <div class="school-card-top">
      <span class="school-seal" :style="{ '--seal': group.university.color }"
        ><span>{{ group.university.initials }}</span
        ><small>UNIVERSITY</small></span
      >
      <div class="school-card-flags">
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
