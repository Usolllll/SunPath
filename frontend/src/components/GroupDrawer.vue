<script setup lang="ts">
import type { Group } from "../api/types";
import TrendChart from "./TrendChart.vue";
import RiskBadge from "./RiskBadge.vue";
import { usePlanner } from "../stores/planner";
import { number } from "../utils/format";
defineProps<{ group: Group | null }>();
const open = defineModel<boolean>({ required: true });
const planner = usePlanner();
</script>
<template>
  <el-drawer v-model="open" title="院校与专业组分析" size="min(620px, 100%)"
    ><div v-if="group" class="detail-body">
      <div class="section-heading">
        <div>
          <h2>{{ group.university.name }}</h2>
          <p>{{ group.university.city }} · {{ group.university.level }}</p>
        </div>
        <RiskBadge :risk="group.risk" />
      </div>
      <p>{{ group.university.description }}</p>
      <div class="notice compact">
        模拟数据 · {{ group.province }}生源 · {{ group.year }} 年方案参考
      </div>
      <h3>
        {{ group.name }} <span class="muted">{{ group.code }}</span>
      </h3>
      <p>{{ group.majors.join(" / ") }}</p>
      <div class="detail-grid">
        <div>
          <small>选科要求</small
          ><strong>{{
            group.required_subjects.join(" + ") || "不限选科"
          }}</strong>
        </div>
        <div>
          <small>模拟招生计划</small><strong>{{ group.seats }} 人</strong>
        </div>
        <div>
          <small>参考学费 / 年</small
          ><strong>¥ {{ number(group.tuition) }}</strong>
        </div>
        <div>
          <small>加权参考位次</small
          ><strong>{{ number(group.baseline_rank) }}</strong>
        </div>
      </div>
      <h3>历年录取位次趋势</h3>
      <p
        v-if="group.history_rank_min != null && group.history_rank_max != null"
        class="notice compact"
      >
        近三年位次范围（模拟）：{{ number(group.history_rank_min) }} –
        {{
          number(group.history_rank_max)
        }}
        位。位次值越小排名越靠前，该区间不是当年录取线。
      </p>
      <TrendChart
        v-if="group.history.length"
        :groups="[group]"
        :height="230"
      /><el-empty v-else description="该年份暂无模拟录取数据" />
      <el-table :data="group.history" size="small"
        ><el-table-column prop="year" label="年份" /><el-table-column
          prop="score"
          label="最低分（模拟）" /><el-table-column
          prop="rank"
          label="最低位次（模拟）"
      /></el-table>
      <template v-if="group.reasons"
        ><h3>为什么推荐</h3>
        <p v-for="reason in group.reasons" :key="reason" class="reason">
          ✓ {{ reason }}
        </p></template
      >
      <div class="notice">
        <strong>填报提示</strong>
        <p>
          {{
            group.warnings?.join("；") ||
            "模拟样本仅供原型演示。实际招生专业、选科、计划和学费请核实官方信息。"
          }}
        </p>
      </div>
      <el-button
        v-if="group.risk"
        type="primary"
        size="large"
        @click="planner.add(group)"
        >加入我的志愿方案</el-button
      ><el-button
        v-else
        type="primary"
        @click="
          open = false;
          $router.push('/analysis');
        "
        >根据我的画像智能匹配</el-button
      >
    </div></el-drawer
  >
</template>
