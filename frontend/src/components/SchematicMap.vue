<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Maximize2, MapPin } from "lucide-vue-next";
import * as echarts from "echarts/core";
import { MapChart, ScatterChart } from "echarts/charts";
import { GeoComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { CatalogUniversity } from "../api/types";
import chinaGeo from "../assets/china-provinces.json";
import {
  CHINA_MAP_NAME,
  MAP_ATTRIBUTION,
  buildSchematicOption,
  focusView,
} from "../utils/schematicMap";

echarts.use([MapChart, ScatterChart, GeoComponent, TooltipComponent, CanvasRenderer]);
// 内置省级行政区划底图：不请求任何第三方地图 SDK 或瓦片服务，零 Key、可离线运行。
echarts.registerMap(CHINA_MAP_NAME, chinaGeo as never);

const props = defineProps<{
  schools: CatalogUniversity[];
  selectedId: number | null;
}>();
const emit = defineEmits<{ select: [id: number] }>();
const host = ref<HTMLDivElement>();
const ready = ref(false);
const failed = ref(false);
const zoom = ref(1.2);
const locatedCount = computed(
  () => props.schools.filter((school) => school.location).length,
);
let chart: echarts.EChartsType | undefined;
let resize: ResizeObserver | undefined;
let disposed = false;

function render() {
  if (!chart || disposed) return;
  const selected = focusView(props.schools, props.selectedId);
  const option = buildSchematicOption(
    props.schools,
    props.selectedId,
    selected ? { center: selected.center, zoom: selected.zoom } : undefined,
  );
  chart.setOption(option as unknown as echarts.EChartsCoreOption, true);
  zoom.value = option.geo.zoom;
}
function resetView() {
  if (!chart) return;
  chart.setOption({
    geo: { center: [104, 35.5], zoom: 1.2 },
  });
  zoom.value = 1.2;
}
function focusSelected() {
  render();
}
onMounted(() => {
  if (!host.value) return;
  try {
    chart = echarts.init(host.value);
  } catch {
    failed.value = true;
    return;
  }
  chart.on("click", (params) => {
    const id = (params.data as { schoolId?: number } | undefined)?.schoolId;
    if (typeof id === "number") emit("select", id);
  });
  chart.on("georoam", () => {
    const option = chart?.getOption() as
      | { geo?: { zoom?: number }[] }
      | undefined;
    const value = option?.geo?.[0]?.zoom;
    if (typeof value === "number") zoom.value = value;
  });
  render();
  ready.value = true;
  resize = new ResizeObserver(() => chart?.resize());
  resize.observe(host.value);
});
watch(() => [props.schools, props.selectedId] as const, render);
defineExpose({ focusSelected, resetView });
onBeforeUnmount(() => {
  disposed = true;
  resize?.disconnect();
  chart?.dispose();
  chart = undefined;
});
</script>

<template>
  <div class="schematic-map-shell">
    <div class="map-stage">
      <div
        ref="host"
        class="schematic-map"
        :data-zoom="zoom.toFixed(2)"
        aria-label="院校分布示意图（内置中国省级行政区划底图）"
      ></div>
      <div class="map-caption">
        <MapPin :size="14" /><span
          >院校分布 <strong>{{ locatedCount }}</strong> 所</span
        >
      </div>
      <button
        v-if="ready"
        class="map-fit"
        type="button"
        @click="resetView"
        aria-label="显示全部筛选院校"
      >
        <Maximize2 :size="15" />显示全部
      </button>
      <div v-if="failed" class="map-empty" role="status">
        图表组件初始化失败，院校列表和招生查询仍可正常使用。
      </div>
      <div v-else-if="ready && !locatedCount" class="map-empty">
        {{
          schools.length ? "这些学校尚未收录参考坐标" : "暂无符合筛选条件的院校"
        }}
      </div>
    </div>
    <div class="map-legend">
      <span><i></i>学校参考位置</span
      ><span>{{ MAP_ATTRIBUTION }}</span
      ><span class="roam-hint">滚轮缩放 · 拖动平移 · 点击点位选校</span>
    </div>
  </div>
</template>

<style scoped>
.schematic-map-shell {
  min-width: 0;
  isolation: isolate;
  background: #edf2f5;
}
.map-stage {
  position: relative;
}
.schematic-map {
  height: 570px;
  width: 100%;
}
.map-caption,
.map-fit {
  position: absolute;
  top: 18px;
  z-index: 5;
  background: #fff;
  border: 1px solid #e1e7ef;
  border-radius: 7px;
  box-shadow: 0 3px 12px #243b5210;
  display: flex;
  align-items: center;
  gap: 7px;
  color: #49627e;
  font-size: 11px;
  padding: 10px 12px;
}
.map-caption {
  left: 18px;
}
.map-caption strong {
  color: #2766b3;
  padding: 0 3px;
}
.map-fit {
  right: 65px;
  cursor: pointer;
}
.map-fit:hover {
  background: #f5f8fc;
}
.map-legend {
  min-height: 40px;
  background: #f8fafc;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 9px;
  color: #7e91a8;
  border-top: 1px solid #e6ecf2;
}
.map-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.map-legend i {
  width: 7px;
  height: 7px;
  background: #397cc9;
  border-radius: 50%;
}
.map-empty {
  position: absolute;
  top: 46%;
  left: 0;
  right: 0;
  text-align: center;
  background: #ffffffdc;
  padding: 20px;
  color: #6f8199;
  font-size: 12px;
  pointer-events: none;
  z-index: 4;
}
@media (max-width: 760px) {
  .schematic-map {
    height: 350px;
  }
  .roam-hint {
    display: none !important;
  }
  .map-caption,
  .map-fit {
    font-size: 10px;
    padding: 9px;
  }
  .map-caption {
    left: 54px;
  }
}
</style>
