<script setup lang="ts">
import { ArrowUpRight, MapPin, Plus, Check } from "lucide-vue-next";
import type { Group } from "../api/types";
import RiskBadge from "./RiskBadge.vue";
import { number } from "../utils/format";
import { usePlanner } from "../stores/planner";
defineProps<{ group: Group }>();
defineEmits<{ detail: [group: Group] }>();
const planner = usePlanner();
</script>
<template>
  <article class="school-card">
    <div class="school-card-top">
      <span class="school-seal" :style="{ '--seal': group.university.color }"
        ><span>{{ group.university.initials }}</span
        ><small>UNIVERSITY</small></span
      ><RiskBadge :risk="group.risk" />
    </div>
    <button class="school-title" @click="$emit('detail', group)">
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
    </div>
    <div class="school-card-bottom">
      <button class="text-button" @click="$emit('detail', group)">
        查看分析 <ArrowUpRight :size="14" /></button
      ><button
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
