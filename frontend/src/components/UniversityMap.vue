<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import type { CatalogUniversity } from "../api/types";
import { Maximize2, RefreshCw, MapPin } from "lucide-vue-next";

const props = defineProps<{
  schools: CatalogUniversity[];
  selectedId: number | null;
}>();
const emit = defineEmits<{ select: [id: number] }>();
const host = ref<HTMLDivElement>();
const tileFailed = ref(false);
const located = computed(() => props.schools.filter((s) => s.location));
let map: L.Map | undefined;
let tiles: L.TileLayer;
let clusters: L.MarkerClusterGroup;
let resize: ResizeObserver;
const markers = new Map<number, L.Marker>();

function icon(active: boolean, city = false) {
  return L.divIcon({
    className:
      "university-map-pin" +
      (active ? " is-selected" : "") +
      (city ? " is-city" : ""),
    html: "<span></span>",
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}
function fit() {
  if (!map) return;
  const bounds = L.latLngBounds(
    located.value.map((s) => [s.location!.latitude, s.location!.longitude]),
  );
  if (bounds.isValid())
    map.fitBounds(bounds, { padding: [55, 55], maxZoom: 12, animate: false });
  else map.setView([34, 110], 4);
}
function selectMarker() {
  if (!map) return;
  markers.forEach((marker, id) =>
    marker.setIcon(
      icon(
        id === props.selectedId,
        props.schools.find((s) => s.id === id)?.location?.precision === "city",
      ),
    ),
  );
  const marker = props.selectedId ? markers.get(props.selectedId) : undefined;
  if (marker)
    clusters.zoomToShowLayer(marker, () => {
      if (
        !map ||
        props.selectedId === null ||
        markers.get(props.selectedId) !== marker
      )
        return;
      map.panTo(marker.getLatLng());
      marker.openTooltip();
    });
}
function draw() {
  if (!map) return;
  clusters.clearLayers();
  markers.clear();
  for (const school of located.value) {
    const location = school.location!;
    const label = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = school.name;
    const sub = document.createElement("div");
    sub.textContent = `${school.region} · ${school.city} · ${school.group_count} 个专业组`;
    const precision = document.createElement("div");
    precision.textContent = location.label;
    label.append(title, sub, precision);
    const marker = L.marker([location.latitude, location.longitude], {
      icon: icon(school.id === props.selectedId, location.precision === "city"),
      title: school.name,
      alt: school.name,
      keyboard: true,
    });
    marker.bindTooltip(label, { direction: "top", offset: [0, -12] });
    marker.on("click", () => emit("select", school.id));
    markers.set(school.id, marker);
    clusters.addLayer(marker);
  }
  fit();
}
onMounted(() => {
  map = L.map(host.value!, {
    minZoom: 3,
    maxZoom: 18,
    scrollWheelZoom: false,
    zoomControl: false,
    worldCopyJump: true,
  }).setView([34, 110], 4);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
  // Browser cache and Referer are kept intact; no prefetching or geocoding requests.
  tiles = L.tileLayer(
    import.meta.env.VITE_MAP_TILE_URL ||
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom: 19,
      attribution:
        import.meta.env.VITE_MAP_ATTRIBUTION ||
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    },
  ).addTo(map);
  tiles.on("tileerror", () => {
    tileFailed.value = true;
  });
  clusters = L.markerClusterGroup({
    maxClusterRadius: 38,
    showCoverageOnHover: false,
    iconCreateFunction: (cluster) =>
      L.divIcon({
        html: `<span>${cluster.getChildCount()}</span>`,
        className: "university-map-cluster",
        iconSize: [38, 38],
      }),
  }).addTo(map);
  resize = new ResizeObserver(() => {
    map?.invalidateSize();
    if (props.selectedId === null) fit();
  });
  resize.observe(host.value!);
  draw();
});
watch(() => props.schools, draw);
watch(() => props.selectedId, selectMarker);
defineExpose({ focusSelected: selectMarker });
onBeforeUnmount(() => {
  resize?.disconnect();
  map?.remove();
  map = undefined;
});
</script>

<template>
  <div class="university-map-shell">
    <div ref="host" class="university-map" aria-label="院校地理位置地图"></div>
    <div class="map-caption">
      <MapPin :size="14" /><span
        >院校分布 <strong>{{ located.length }}</strong> 所</span
      >
    </div>
    <button
      class="map-fit"
      type="button"
      @click="fit"
      aria-label="显示全部筛选院校"
    >
      <Maximize2 :size="15" />显示全部
    </button>
    <div v-if="tileFailed" class="map-warning" role="status">
      底图部分加载失败，请检查网络。院校位置仍可点击。<button
        @click="
          tileFailed = false;
          tiles.redraw();
        "
      >
        <RefreshCw :size="12" />重试底图
      </button>
    </div>
    <div v-if="!located.length" class="map-empty">
      {{
        schools.length ? "这些学校尚未收录参考坐标" : "暂无符合筛选条件的院校"
      }}
    </div>
    <div class="map-legend">
      <i></i>学校参考位置 <span>数字为邻近院校数量，点击展开</span>
    </div>
  </div>
</template>

<style scoped>
:deep(.university-map-pin.is-city:not(.is-selected) span) {
  background: #fff;
  border: 2px dashed #657c94;
}
.university-map-shell {
  position: relative;
  min-width: 0;
  isolation: isolate;
  background: #e9f0f3;
}
.university-map {
  height: 610px;
  width: 100%;
  z-index: 0;
  font-family: inherit;
}
.map-caption,
.map-fit {
  position: absolute;
  top: 18px;
  z-index: 1;
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
  right: 18px;
  cursor: pointer;
}
.map-fit:hover {
  background: #f5f8fc;
}
.map-legend {
  position: absolute;
  bottom: 38px;
  left: 14px;
  background: #ffffffed;
  padding: 7px 10px;
  border-radius: 5px;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 9px;
  color: #57708a;
}
.map-legend i {
  width: 7px;
  height: 7px;
  background: #337bca;
  border-radius: 50%;
}
.map-legend span {
  color: #8795a7;
  margin-left: 6px;
}
.map-warning {
  position: absolute;
  top: 72px;
  left: 18px;
  right: 18px;
  background: #fff7e8;
  padding: 10px;
  font-size: 10px;
  z-index: 2;
  border: 1px solid #e8d6b2;
  border-radius: 6px;
  color: #886b3b;
}
.map-warning button {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  margin-left: 8px;
  color: #326eb5;
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
}
:deep(.university-map-pin) {
  background: transparent;
  border: 0;
  display: grid;
  place-items: center;
}
:deep(.university-map-pin span) {
  display: block;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #397cc9;
  border: 3px solid #fff;
  box-shadow: 0 1px 7px #174b7a66;
  transition: transform 0.15s;
}
:deep(.university-map-pin.is-selected span) {
  background: #dc9b40;
  width: 19px;
  height: 19px;
  box-shadow: 0 0 0 6px #eab45d44;
}
:deep(.university-map-cluster) {
  border-radius: 50%;
  background: #bad4eb80;
  padding: 4px;
}
:deep(.university-map-cluster span) {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  background: #2e6eac;
  color: #fff;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
}
:deep(.leaflet-tooltip) {
  padding: 10px 12px;
  color: #365576;
  border-color: #dce6f0;
  line-height: 1.8;
}
:deep(.leaflet-tooltip strong) {
  font-size: 12px;
}
:deep(.leaflet-tooltip div div) {
  color: #8b9aaf;
  font-size: 10px;
}
:deep(.leaflet-control-attribution) {
  font-size: 9px;
}
@media (max-width: 760px) {
  .university-map {
    height: 390px;
  }
  .map-legend span {
    display: none;
  }
}
</style>
