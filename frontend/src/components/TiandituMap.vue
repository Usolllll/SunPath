<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { Maximize2, RefreshCw, MapPin, ShieldCheck } from "lucide-vue-next";
import type { CatalogUniversity } from "../api/types";
import { api } from "../api";
import { hasTiandituKey, loadTianditu } from "../utils/tianditu";
import { createUniversityMap } from "../utils/universityMap";

const props = defineProps<{
  schools: CatalogUniversity[];
  selectedId: number | null;
}>();
const emit = defineEmits<{ select: [id: number] }>();
const host = ref<HTMLDivElement>();
const located = computed(() => props.schools.filter((s) => s.location));
// Key 优先级：后端 /api/map/config（部署方在 backend/.env 配置，换 Key 不必重新构建前端）
// → 构建期 VITE_TIANDITU_KEY（纯静态部署的兜底）。
const key = ref("");
const resolving = ref(true);
const configured = computed(() => hasTiandituKey(key.value));
const ready = ref(false);
const loading = ref(false);
const error = ref("");
const tileFailed = ref(false);
const mapId = `sunpath-tianditu-${Math.random().toString(36).slice(2)}`;
let adapter: ReturnType<typeof createUniversityMap> | undefined;
let resize: ResizeObserver | undefined;
let disposed = false;

async function resolveKey(): Promise<string> {
  try {
    const { data: config } = await api.mapConfig();
    if (config.configured && hasTiandituKey(config.key)) return config.key.trim();
  } catch {
    // 后端不可用时回退构建期变量，静态部署仍可工作
  }
  return (import.meta.env.VITE_TIANDITU_KEY || "").trim();
}

async function initialize() {
  if (!configured.value || loading.value || disposed) return;
  loading.value = true;
  ready.value = false;
  error.value = "";
  tileFailed.value = false;
  adapter?.destroy();
  adapter = undefined;
  host.value?.replaceChildren();
  try {
    const T = await loadTianditu(key.value);
    if (disposed || !host.value) return;
    adapter = createUniversityMap(T, mapId, (id) => emit("select", id));
    adapter.update(props.schools, props.selectedId);
    if (props.selectedId !== null) adapter.select(props.selectedId);
    ready.value = true;
  } catch {
    error.value = "天地图未能加载，请检查网络、Key 权限和域名白名单后重试。";
  } finally {
    loading.value = false;
  }
}
function focusSelected() {
  adapter?.select(props.selectedId);
}
function onResourceError(event: Event) {
  if (
    event.target instanceof HTMLImageElement &&
    /^https?:/.test(event.target.src)
  )
    tileFailed.value = true;
}
onMounted(async () => {
  host.value?.addEventListener("error", onResourceError, true);
  resize = new ResizeObserver(() => {
    adapter?.resize();
    if (props.selectedId === null) adapter?.fit();
  });
  if (host.value) resize.observe(host.value);
  key.value = await resolveKey();
  resolving.value = false;
  void initialize();
});
watch(
  () => props.schools,
  (schools) => adapter?.update(schools, props.selectedId),
);
watch(() => props.selectedId, focusSelected);
defineExpose({ focusSelected });
onBeforeUnmount(() => {
  disposed = true;
  resize?.disconnect();
  host.value?.removeEventListener("error", onResourceError, true);
  adapter?.destroy();
  adapter = undefined;
});
</script>

<template>
  <div class="university-map-shell">
    <div class="map-stage">
      <div
        :id="mapId"
        ref="host"
        class="university-map"
        aria-label="天地图院校地理位置地图"
      ></div>
      <div class="map-caption">
        <MapPin :size="14" /><span
          >院校分布 <strong>{{ located.length }}</strong> 所</span
        >
      </div>
      <button
        v-if="ready"
        class="map-fit"
        type="button"
        @click="adapter?.fit()"
        aria-label="显示全部筛选院校"
      >
        <Maximize2 :size="15" />显示全部
      </button>
      <div
        v-if="resolving || !configured || error || loading"
        class="map-state"
        role="status"
      >
        <span class="map-state-icon"
          ><ShieldCheck :size="30" :stroke-width="1.4"
        /></span>
        <h3>
          {{
            resolving
              ? "正在加载地图配置"
              : !configured
                ? "天地图服务待启用"
                : loading
                  ? "正在加载天地图"
                  : "地图暂时无法加载"
          }}
        </h3>
        <p v-if="resolving">正在读取后端地图配置，请稍候。</p>
        <p v-else-if="!configured">
          请联系管理员配置天地图 Web 端 Key。院校列表和招生查询仍可正常使用。
        </p>
        <p v-else-if="loading">正在连接天地图官方地图服务，请稍候。</p>
        <p v-else>{{ error }}</p>
        <a
          v-if="!resolving && !configured"
          href="https://console.tianditu.gov.cn/"
          target="_blank"
          rel="noopener noreferrer"
          >前往天地图控制台 ↗</a
        >
        <button v-else-if="!loading" class="map-retry" @click="initialize">
          <RefreshCw :size="13" />重新加载
        </button>
      </div>
      <div v-if="ready && tileFailed" class="map-warning" role="status">
        部分地图资源加载失败，请检查网络和服务授权。<button @click="initialize">
          <RefreshCw :size="12" />重试
        </button>
      </div>
      <div v-if="ready && !located.length" class="map-empty">
        {{
          schools.length ? "这些学校尚未收录参考坐标" : "暂无符合筛选条件的院校"
        }}
      </div>
    </div>
    <!-- Keep this outside the SDK canvas; never cover the official logo, approval number or copyright. -->
    <div class="map-legend">
      <span><i></i>学校参考位置</span
      ><span
        >底图服务：<a
          href="https://www.tianditu.gov.cn/"
          target="_blank"
          rel="noopener noreferrer"
          >天地图</a
        ></span
      ><span class="cluster-hint">点击聚合标记可展开</span
      ><span class="wheel-hint">滚轮缩放</span>
    </div>
  </div>
</template>

<style scoped>
.university-map-shell {
  min-width: 0;
  isolation: isolate;
  background: #edf2f5;
}
.map-stage {
  position: relative;
}
.university-map {
  height: 570px;
  width: 100%;
  font-family: inherit;
}
.map-caption,
.map-fit {
  position: absolute;
  top: 18px;
  z-index: 450;
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
  left: 54px;
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
.map-legend a {
  color: #4b78ab;
}
.map-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 13px;
  text-align: center;
  padding: 65px 28px;
  color: #68829f;
  background: radial-gradient(
    ellipse at 50% 40%,
    #fff 0%,
    #f1f5f8 65%,
    #e9f0f4 100%
  );
}
.map-state-icon {
  width: 66px;
  height: 66px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  color: #6c8eac;
  background: #e6edf5;
  margin-bottom: 7px;
}
.map-state h3 {
  font-size: 17px;
  color: #3d5b7a;
  font-weight: 500;
}
.map-state p {
  max-width: 330px;
  font-size: 12px;
  line-height: 1.9;
}
.map-state a,
.map-retry {
  font-size: 11px;
  color: #3573b7;
  margin-top: 5px;
}
.map-retry {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid #cbd9e9;
  border-radius: 5px;
  background: #fff;
}
.map-warning {
  position: absolute;
  top: 75px;
  left: 18px;
  right: 18px;
  z-index: 450;
  padding: 10px;
  background: #fff7e8;
  border: 1px solid #e8d6b2;
  border-radius: 6px;
  font-size: 10px;
  color: #886b3b;
}
.map-warning button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #326eb5;
  margin-left: 8px;
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
  z-index: 450;
}
:deep(.university-map-info) {
  color: #47627e;
  line-height: 1.8;
  font-family: inherit;
}
:deep(.university-map-info strong) {
  font-size: 13px;
}
:deep(.university-map-info p) {
  font-size: 10px;
  margin-top: 4px;
  color: #8294a9;
}
@media (max-width: 760px) {
  .university-map {
    height: 350px;
  }
  .cluster-hint {
    display: none !important;
  }
  .wheel-hint {
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
  .map-state h3 {
    font-size: 15px;
  }
  .map-state p {
    font-size: 11px;
  }
}
</style>
