<script setup lang="ts">
import { onMounted, ref } from "vue";
import type { CatalogUniversity } from "../api/types";
import { api } from "../api";
import TiandituMap from "./TiandituMap.vue";
import SchematicMap from "./SchematicMap.vue";

/**
 * 地图容器：按后端 /api/map/config 选择底图来源。
 * - schematic（默认，无任何账号/Key）：内置省级行政区划 + 院校点位，零外部依赖；
 * - tianditu（可选）：部署方在 backend/.env 配置自己的 TIANDITU_WEB_KEY 后启用。
 */
const props = defineProps<{
  schools: CatalogUniversity[];
  selectedId: number | null;
}>();
const emit = defineEmits<{ select: [id: number] }>();
const provider = ref<"tianditu" | "schematic" | null>(null);
const mapRef = ref<InstanceType<typeof TiandituMap> | InstanceType<typeof SchematicMap>>();

onMounted(async () => {
  try {
    const { data } = await api.mapConfig();
    provider.value = data.provider === "tianditu" ? "tianditu" : "schematic";
  } catch {
    // 后端不可用时给零依赖的示意图，地图仍可用
    provider.value = "schematic";
  }
});
function focusSelected() {
  mapRef.value?.focusSelected();
}
defineExpose({ focusSelected });
</script>

<template>
  <div v-if="!provider" class="map-config-loading" role="status">
    正在加载地图配置…
  </div>
  <TiandituMap
    v-else-if="provider === 'tianditu'"
    ref="mapRef"
    :schools="props.schools"
    :selected-id="props.selectedId"
    @select="emit('select', $event)"
  />
  <SchematicMap
    v-else
    ref="mapRef"
    :schools="props.schools"
    :selected-id="props.selectedId"
    @select="emit('select', $event)"
  />
</template>

<style scoped>
.map-config-loading {
  height: 570px;
  display: grid;
  place-items: center;
  background: #edf2f5;
  color: #7b8ea5;
  font-size: 12px;
}
@media (max-width: 760px) {
  .map-config-loading {
    height: 350px;
  }
}
</style>
