<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, nextTick } from "vue";
import { useRoute } from "vue-router";
import {
  Search,
  RotateCcw,
  ArrowUpRight,
  Database,
  Info,
  MapPin,
} from "lucide-vue-next";
import type { Group, CatalogUniversity } from "../api/types";
import { api } from "../api";
import { useAuth } from "../stores/auth";
import GroupDrawer from "../components/GroupDrawer.vue";
import UniversityMap from "../components/UniversityMap.vue";
import RealDataPanel from "../components/RealDataPanel.vue";
import { number } from "../utils/format";
const auth = useAuth();
const route = useRoute();
const tab = ref(route.query.tab === "realdata" ? "realdata" : "schools");
const items = ref<Group[]>([]);
const total = ref(0);
const regions = ref<string[]>([]);
const busy = ref(false);
const failed = ref(false);
const detail = ref<Group | null>(null);
const drawer = ref(false);
const universities = ref<CatalogUniversity[]>([]);
const selectedId = ref<number | null>(null);
const schoolPage = ref(1);
const detailBusy = ref(false);
const mapView = ref<InstanceType<typeof UniversityMap>>();
const selectedSchool = computed(() =>
  universities.value.find((s) => s.id === selectedId.value),
);
const schoolItems = computed(() =>
  universities.value.slice((schoolPage.value - 1) * 6, schoolPage.value * 6),
);
const activePage = computed({
  get: () => (tab.value === "schools" ? schoolPage.value : filters.page),
  set: (value) => {
    if (tab.value === "schools") schoolPage.value = value;
    else filters.page = value;
  },
});
const filters = reactive({
  q: "",
  region: "",
  level: "",
  subject: "",
  province: auth.user?.profile?.province || "浙江",
  year: auth.user?.profile?.exam_year || 2026,
  page: 1,
  page_size: 12,
});
let request = 0;
async function load(reset = false) {
  if (reset) {
    filters.page = 1;
    schoolPage.value = 1;
  }
  const seq = ++request;
  busy.value = true;
  failed.value = false;
  try {
    const { data } = await api.catalog(filters);
    if (seq === request) {
      items.value = data.items;
      total.value = data.total;
      regions.value = data.regions;
      universities.value = data.universities || [];
      if (!universities.value.some((s) => s.id === selectedId.value))
        selectedId.value = null;
    }
  } catch {
    if (seq === request) failed.value = true;
  } finally {
    if (seq === request) busy.value = false;
  }
}
function reset() {
  Object.assign(filters, {
    q: "",
    region: "",
    level: "",
    subject: "",
    page: 1,
  });
  schoolPage.value = 1;
  void load();
}
function show(group: Group) {
  selectedId.value = group.university.id;
  detail.value = group;
  drawer.value = true;
}
function selectSchool(id: number) {
  const sameSelection = selectedId.value === id;
  selectedId.value = id;
  const index = universities.value.findIndex((s) => s.id === id);
  if (index >= 0) schoolPage.value = Math.floor(index / 6) + 1;
  if (sameSelection) void nextTick(() => mapView.value?.focusSelected());
}
async function openSchool(school: CatalogUniversity) {
  selectedId.value = school.id;
  detailBusy.value = true;
  try {
    const { data } = await api.catalogDetail(school.group_ids[0], {
      province: filters.province,
      year: filters.year,
    });
    show(data);
  } catch {
    // The shared API interceptor presents the request failure to the user.
  } finally {
    detailBusy.value = false;
  }
}
watch(tab, () => {
  filters.page = 1;
  schoolPage.value = 1;
  // 「官方真实投档」页签使用独立的真实数据面板，不触发模拟样本库查询
  if (tab.value !== "realdata") void load();
});
onMounted(() => {
  if (tab.value !== "realdata") void load();
});
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">EXPLORE THE POSSIBILITIES</div>
      <h1>看见更多大学，发现更多可能</h1>
      <p>从地图发现心仪院校，将每一次探索落在真实的地理位置上。</p>
    </div>
    <span class="data-source-pill"
      ><Database :size="14" />模拟样本库 + 官方投档数据 · 2026</span
    >
  </div>
  <section class="panel data-panel">
    <div class="content-tabs">
      <button
        v-for="t in [
          { id: 'schools', label: '高校信息' },
          { id: 'majors', label: '专业信息' },
          { id: 'scores', label: '历年录取' },
          { id: 'enrollment', label: '招生计划' },
          { id: 'realdata', label: '官方真实投档' },
        ]"
        :key="t.id"
        :class="{ active: tab === t.id }"
        @click="tab = t.id"
      >
        {{ t.label }}
      </button>
    </div>
    <RealDataPanel v-if="tab === 'realdata'" />
    <template v-else>
    <form class="filter-toolbar" @submit.prevent="load(true)">
      <el-input
        v-model="filters.q"
        placeholder="搜索院校名称 / 专业关键词"
        clearable
        @clear="load(true)"
        ><template #prefix><Search :size="16" /></template></el-input
      ><el-select
        v-model="filters.region"
        placeholder="院校地区"
        clearable
        @change="load(true)"
        ><el-option
          v-for="r in regions"
          :key="r"
          :value="r"
          :label="r" /></el-select
      ><el-select
        v-model="filters.level"
        placeholder="院校层次"
        clearable
        @change="load(true)"
        ><el-option
          v-for="l in ['985', '211', '双一流', '省重点']"
          :key="l"
          :value="l"
          :label="l" /></el-select
      ><el-select
        v-model="filters.subject"
        placeholder="选科要求"
        clearable
        @change="load(true)"
        ><el-option
          v-for="s in ['物理', '化学']"
          :key="s"
          :value="s"
          :label="s" /></el-select
      ><el-button type="primary" native-type="submit">查询</el-button
      ><el-button @click="reset" aria-label="重置筛选"
        ><RotateCcw :size="15"
      /></el-button>
    </form>
    <div class="data-context">
      <span>生源省份</span
      ><el-select v-model="filters.province" @change="load(true)"
        ><el-option
          v-for="p in ['浙江', '江苏', '山东', '广东', '河南', '四川']"
          :key="p"
          :label="p"
          :value="p" /></el-select
      ><span>计划年份</span
      ><el-select v-model="filters.year" @change="load(true)"
        ><el-option
          v-for="year in [2026, 2027]"
          :key="year"
          :value="year"
          :label="`${year} 年`" /></el-select
      ><span class="data-count"
        >{{ universities.length }} 所院校 · {{ total }} 个专业组 ·
        地图展示全部筛选结果</span
      >
    </div>
    <div class="catalog-workspace" v-loading="busy">
      <div class="catalog-directory">
        <div class="directory-heading">
          <div>
            <span class="eyebrow">UNIVERSITY EXPLORER</span>
            <h2>
              {{ tab === "schools" ? "在这里，找到下一站" : "探索院校与专业" }}
            </h2>
          </div>
          <span class="tag">{{ universities.length }} 所</span>
        </div>
        <div class="data-results">
          <div v-if="failed" class="empty-state">
            <p>数据加载失败</p>
            <el-button @click="load()">重新加载</el-button>
          </div>
          <template v-else
            ><div
              v-if="tab === 'schools' && schoolItems.length"
              class="university-list"
            >
              <button
                v-for="school in schoolItems"
                :key="school.id"
                :class="[
                  'university-row',
                  { 'is-selected': selectedId === school.id },
                ]"
                @click="selectSchool(school.id)"
                :aria-pressed="selectedId === school.id"
              >
                <span
                  class="school-seal small"
                  :style="{ '--seal': school.color }"
                  ><span>{{ school.initials }}</span></span
                >
                <div class="university-row-name">
                  <h3>{{ school.name }}</h3>
                  <p>
                    <MapPin :size="11" />{{ school.region }} · {{ school.city
                    }}<span> · {{ school.group_count }} 个专业组</span>
                  </p>
                  <div class="school-tags">
                    <span
                      v-for="level in school.level.split(' / ')"
                      :key="level"
                      class="tag"
                      >{{ level }}</span
                    >
                  </div>
                </div>
                <span class="university-row-action"
                  >{{ school.location ? "地图定位" : "待定位"
                  }}<ArrowUpRight :size="16"
                /></span>
              </button>
            </div>
            <div v-else-if="tab === 'schools'" class="empty-state">
              暂无符合筛选条件的院校
            </div>
            <el-table
              v-else
              :data="items"
              @row-click="show"
              class="clickable-table"
              ><el-table-column label="院校 / 专业组" min-width="230"
                ><template #default="{ row }"
                  ><strong>{{ row.university.name }}</strong>
                  <p class="table-sub">
                    {{ row.name }} · {{ row.code }}
                  </p></template
                ></el-table-column
              ><el-table-column
                v-if="tab === 'majors'"
                label="包含专业"
                min-width="240"
                ><template #default="{ row }">{{
                  row.majors.join(" / ")
                }}</template></el-table-column
              ><el-table-column label="选科要求" min-width="120"
                ><template #default="{ row }">{{
                  row.required_subjects.join(" + ") || "不限选科"
                }}</template></el-table-column
              ><template v-if="tab === 'scores'"
                ><el-table-column
                  v-for="year in [2023, 2024, 2025]"
                  :key="year"
                  :label="`${year} 分数 / 位次`"
                  min-width="145"
                  ><template #default="{ row }"
                    >{{
                      row.history.find((h: { year: number }) => h.year === year)
                        ?.score ?? "暂无"
                    }}
                    /
                    {{
                      number(
                        row.history.find(
                          (h: { year: number }) => h.year === year,
                        )?.rank,
                      )
                    }}</template
                  ></el-table-column
                ></template
              ><template v-else
                ><el-table-column
                  :label="`${filters.year} 计划`"
                  min-width="100"
                  ><template #default="{ row }"
                    >{{ row.seats || "暂无"
                    }}{{ row.seats ? " 人" : "" }}</template
                  ></el-table-column
                ><el-table-column
                  v-if="tab === 'enrollment'"
                  label="模拟学费 / 年"
                  min-width="120"
                  ><template #default="{ row }"
                    >¥ {{ number(row.tuition) }}</template
                  ></el-table-column
                ></template
              ><el-table-column width="90" label="详情"
                ><template #default
                  ><ArrowUpRight
                    :size="17"
                    class="blue-text" /></template></el-table-column
              ><template #empty>暂无符合筛选条件的模拟数据</template></el-table
            ></template
          >
        </div>
        <div class="pagination-row">
          <span>模拟数据，仅供产品演示</span
          ><el-pagination
            v-model:current-page="activePage"
            :page-size="tab === 'schools' ? 6 : filters.page_size"
            :total="tab === 'schools' ? universities.length : total"
            layout="prev, pager, next"
            @current-change="tab !== 'schools' && load()"
          />
        </div>
      </div>
      <div class="catalog-map-column">
        <UniversityMap
          ref="mapView"
          :schools="universities"
          :selected-id="selectedId"
          @select="selectSchool"
        />
        <div v-if="selectedSchool" class="map-school-detail">
          <div>
            <span class="eyebrow">YOUR NEXT DESTINATION</span>
            <h3>{{ selectedSchool.name }}</h3>
            <p>
              {{ selectedSchool.city }} · {{ selectedSchool.category }} ·
              {{ selectedSchool.group_count }} 个专业组
            </p>
            <p class="coordinate-note">
              {{ selectedSchool.location?.label || "尚未收录参考坐标" }}
              <a
                v-if="selectedSchool.location"
                :href="selectedSchool.location.source_url"
                target="_blank"
                rel="noopener noreferrer"
                >位置来源 ↗</a
              >
            </p>
          </div>
          <el-button
            type="primary"
            :loading="detailBusy"
            @click="openSchool(selectedSchool)"
            >查看专业组<ArrowUpRight :size="14"
          /></el-button>
        </div>
        <div v-else class="map-selection-hint">
          <MapPin :size="18" />
          <div>
            <strong>把理想大学，放进你的未来版图</strong>
            <p>
              点击左侧院校或地图标记，查看位置与专业组。位置仅作地域参考，不代表全部校区。
            </p>
          </div>
        </div>
      </div>
    </div>
    </template>
  </section>
  <div v-if="tab !== 'realdata'" class="data-disclaimer">
    <Info :size="15" />「高校信息 / 专业信息 / 历年录取 / 招生计划」为模拟样本库，不含真实招生数据，仅供产品演示；2027
    年暂无模拟计划。官方真实投档数据见「官方真实投档」页签，正式填报请查阅省考试院和高校招生章程。
  </div>
  <GroupDrawer v-model="drawer" :group="detail" />
</template>

<style scoped>
.data-panel {
  overflow: hidden;
}
.catalog-workspace {
  display: grid;
  grid-template-columns: minmax(310px, 0.85fr) minmax(0, 1.4fr);
  border-top: 1px solid var(--line);
}
.catalog-directory {
  max-height: 726px;
  min-width: 0;
  background: #fff;
  display: flex;
  flex-direction: column;
}
.directory-heading {
  padding: 23px 24px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.directory-heading .eyebrow {
  font-size: 8px;
  letter-spacing: 1.5px;
}
.directory-heading h2 {
  font-size: 17px;
  font-weight: 500;
  color: #365474;
  margin-top: 6px;
}
.catalog-directory .data-results {
  flex: 1;
  padding: 0 13px;
  min-height: 0;
  overflow: auto;
}
.catalog-directory .university-row {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 20px 12px;
  border-radius: 7px;
  border-bottom: 1px solid #eff2f7;
  text-align: left;
  width: 100%;
}
.catalog-directory .university-row:hover {
  background: #f6f9fd;
}
.catalog-directory .university-row.is-selected {
  background: #edf4fd;
  box-shadow: inset 3px 0 #4e86c8;
}
.catalog-directory .university-row-name {
  flex: 1;
  min-width: 0;
}
.catalog-directory .university-row h3 {
  font-size: 13px;
}
.catalog-directory .university-row p {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  flex-wrap: wrap;
  margin-top: 5px;
}
.catalog-directory .school-tags {
  display: flex;
  gap: 5px;
  margin-top: 7px;
  flex-wrap: wrap;
}
.catalog-directory .tag {
  font-size: 8px;
  padding: 2px 6px;
}
.catalog-directory .university-row-action {
  font-size: 9px;
  display: flex;
  gap: 3px;
  align-items: center;
  white-space: nowrap;
}
.catalog-directory .pagination-row {
  padding: 18px 22px;
  gap: 8px;
  flex-wrap: wrap;
}
.catalog-directory .pagination-row > span {
  font-size: 9px;
}
.catalog-map-column {
  min-width: 0;
  border-left: 1px solid var(--line);
  background: #f8fafc;
}
.map-school-detail,
.map-selection-hint {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  min-height: 116px;
}
.map-school-detail {
  justify-content: space-between;
}
.map-school-detail h3 {
  font-size: 16px;
  color: #345274;
  margin-top: 4px;
}
.map-school-detail p,
.map-selection-hint p {
  font-size: 10px;
  color: #90a0b4;
  margin-top: 5px;
  line-height: 1.8;
}
.map-school-detail .eyebrow {
  font-size: 8px;
}
.map-school-detail .el-button {
  font-size: 11px;
}
.coordinate-note a {
  color: #5681b1;
  margin-left: 5px;
}
.map-selection-hint > svg {
  color: #b99866;
  flex-shrink: 0;
}
.map-selection-hint strong {
  font-size: 12px;
  font-weight: 500;
  color: #59718d;
}
.catalog-directory :deep(.el-table) {
  font-size: 11px;
}
.data-count {
  font-size: 10px;
}
@media (max-width: 1200px) {
  .catalog-workspace {
    grid-template-columns: minmax(290px, 1fr) minmax(0, 1.2fr);
  }
  .catalog-directory .university-row-action {
    display: none;
  }
  .catalog-directory .university-row {
    padding: 20px 8px;
  }
  .map-school-detail {
    flex-wrap: wrap;
    padding: 16px;
  }
}
@media (max-width: 1000px) {
  .catalog-directory {
    max-height: none;
  }
  .catalog-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .catalog-map-column {
    grid-row: 1;
    border-left: 0;
    border-bottom: 1px solid var(--line);
  }
  .catalog-directory .data-results {
    min-height: 0;
  }
  .catalog-directory .university-row-action {
    display: flex;
  }
}
@media (max-width: 760px) {
  .directory-heading {
    padding: 20px;
  }
  .catalog-directory .university-row {
    padding: 17px 8px;
  }
  .catalog-directory .school-tags {
    display: flex;
  }
  .map-selection-hint {
    padding: 17px;
    min-height: 90px;
  }
  .map-school-detail h3 {
    font-size: 14px;
  }
}
</style>
