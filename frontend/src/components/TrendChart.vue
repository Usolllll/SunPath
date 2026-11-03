<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Group } from "../api/types";
echarts.use([
  LineChart,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer,
]);
const props = defineProps<{
  groups: Group[];
  studentRank?: number;
  height?: number;
}>();
const container = ref<HTMLDivElement>();
let chart: echarts.ECharts | undefined;
let observer: ResizeObserver | undefined;
function render() {
  const years = [
    ...new Set(props.groups.flatMap((g) => g.history.map((h) => h.year))),
  ].sort();
  const colors = ["#3d74d8", "#e8a14b", "#59a79c"];
  const series: Record<string, unknown>[] = props.groups
    .slice(0, 3)
    .map((g, i) => ({
      name: g.university.name,
      type: "line",
      smooth: 0.25,
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: 2.5 },
      itemStyle: { color: colors[i] },
      data: years.map(
        (year) => g.history.find((h) => h.year === year)?.rank ?? null,
      ),
    }));
  if (props.studentRank && years.length)
    series.push({
      name: "我的位次",
      type: "line",
      data: years.map(() => props.studentRank),
      symbol: "none",
      lineStyle: { type: "dashed", width: 1.5, color: "#a4afc0" },
      itemStyle: { color: "#a4afc0" },
    });
  chart?.setOption(
    {
      textStyle: {
        fontFamily: "Inter, Microsoft YaHei, sans-serif",
        color: "#7c899e",
      },
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: number) => `${v.toLocaleString()} 位`,
      },
      legend: {
        bottom: 0,
        icon: "roundRect",
        itemWidth: 12,
        itemHeight: 3,
        textStyle: { fontSize: 11, color: "#77849a" },
        itemGap: 18,
      },
      grid: { left: 54, right: 16, top: 22, bottom: 54 },
      xAxis: {
        type: "category",
        data: years.map(String),
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#e9edf3" } },
        axisTick: { show: false },
        axisLabel: { margin: 15 },
      },
      yAxis: {
        type: "value",
        inverse: true,
        axisLabel: { formatter: (v: number) => `${(v / 1000).toFixed(0)}k` },
        splitLine: { lineStyle: { color: "#eef1f6", type: "dashed" } },
      },
      series,
    },
    true,
  );
}
onMounted(() => {
  if (!container.value) return;
  chart = echarts.init(container.value);
  render();
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(container.value);
});
watch(() => [props.groups, props.studentRank], render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <div
    ref="container"
    :style="{ height: `${height || 245}px`, width: '100%' }"
    role="img"
    aria-label="近三年模拟录取位次趋势图，位次数值越小排名越靠前"
  ></div>
</template>
