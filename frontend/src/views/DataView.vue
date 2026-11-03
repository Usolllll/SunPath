<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  Search,
  RotateCcw,
  ArrowUpRight,
  Database,
  Info,
} from "lucide-vue-next";
import type { Group } from "../api/types";
import { api } from "../api";
import { useAuth } from "../stores/auth";
import GroupDrawer from "../components/GroupDrawer.vue";
import { number } from "../utils/format";
const auth = useAuth();
const tab = ref("schools");
const items = ref<Group[]>([]);
const total = ref(0);
const regions = ref<string[]>([]);
const busy = ref(false);
const failed = ref(false);
const detail = ref<Group | null>(null);
const drawer = ref(false);
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
  if (reset) filters.page = 1;
  const seq = ++request;
  busy.value = true;
  failed.value = false;
  try {
    const { data } = await api.catalog(filters);
    if (seq === request) {
      items.value = data.items;
      total.value = data.total;
      regions.value = data.regions;
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
  void load();
}
function show(group: Group) {
  detail.value = group;
  drawer.value = true;
}
const schoolItems = computed(() => [
  ...new Map(items.value.map((g) => [g.university.id, g])).values(),
]);
onMounted(() => load());
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">EXPLORE THE POSSIBILITIES</div>
      <h1>看见更多大学，发现更多可能</h1>
      <p>院校、专业、历年录取与招生计划，一站式探索。</p>
    </div>
    <span class="data-source-pill"
      ><Database :size="14" />模拟样本库 · 2026</span
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
        ]"
        :key="t.id"
        :class="{ active: tab === t.id }"
        @click="tab = t.id"
      >
        {{ t.label }}
      </button>
    </div>
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
        >共 {{ total }} 个专业组 · 院校按当前页去重展示</span
      >
    </div>
    <div v-loading="busy" class="data-results">
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
            v-for="g in schoolItems"
            :key="g.university.id"
            class="university-row"
            @click="show(g)"
          >
            <span
              class="school-seal small"
              :style="{ '--seal': g.university.color }"
              ><span>{{ g.university.initials }}</span></span
            >
            <div class="university-row-name">
              <h3>{{ g.university.name }}</h3>
              <p>{{ g.university.city }} · {{ g.university.category }}</p>
            </div>
            <div class="school-tags">
              <span
                v-for="l in g.university.level.split(' / ')"
                :key="l"
                class="tag"
                >{{ l }}</span
              >
            </div>
            <span class="university-row-action"
              >查看专业组<ArrowUpRight :size="16"
            /></span>
          </button>
        </div>
        <el-table v-else :data="items" @row-click="show" class="clickable-table"
          ><el-table-column label="院校 / 专业组" min-width="230"
            ><template #default="{ row }"
              ><strong>{{ row.university.name }}</strong>
              <p class="table-sub">{{ row.name }} · {{ row.code }}</p></template
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
                    row.history.find((h: { year: number }) => h.year === year)
                      ?.rank,
                  )
                }}</template
              ></el-table-column
            ></template
          ><template v-else
            ><el-table-column :label="`${filters.year} 计划`" min-width="100"
              ><template #default="{ row }"
                >{{ row.seats || "暂无" }}{{ row.seats ? " 人" : "" }}</template
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
        v-model:current-page="filters.page"
        :page-size="filters.page_size"
        :total="total"
        layout="prev, pager, next"
        @current-change="load()"
      />
    </div>
  </section>
  <div class="data-disclaimer">
    <Info :size="15" />本库不含真实招生数据。2027
    年暂无模拟计划；正式填报请查阅省考试院和高校招生章程。
  </div>
  <GroupDrawer v-model="drawer" :group="detail" />
</template>
