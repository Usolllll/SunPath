<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowRight,
  ArrowUpRight,
  Sparkles,
  ContactRound,
  School,
  Route,
  FolderHeart,
  ChevronRight,
  Info,
  SlidersHorizontal,
  Check,
  Compass,
} from "lucide-vue-next";
import { api } from "../api";
import type { Group, Recommendation } from "../api/types";
import { useAuth } from "../stores/auth";
import { usePlanner } from "../stores/planner";
import { number } from "../utils/format";
import TrendChart from "../components/TrendChart.vue";
import SchoolCard from "../components/SchoolCard.vue";
import GroupDrawer from "../components/GroupDrawer.vue";
const auth = useAuth();
const planner = usePlanner();
const router = useRouter();
const busy = ref(true);
const failed = ref(false);
const stats = ref({ universities: 0, groups: 0, plans: 0, data_label: "" });
const recommendations = ref<Recommendation>({
  items: [],
  counts: { reach: 0, steady: 0, safe: 0 },
  disclaimer: "",
  engine_version: "",
});
const profile = computed(() => auth.user?.profile);
const progress = computed(() =>
  !profile.value ? 0 : stats.value.plans ? 3 : planner.items.length ? 2 : 1,
);
const featured = computed(() =>
  ["reach", "steady", "safe"]
    .map((r) => recommendations.value.items.find((g) => g.risk === r))
    .filter((g): g is Group => !!g),
);
const detail = ref<Group | null>(null);
const drawer = ref(false);
function show(group: Group) {
  detail.value = group;
  drawer.value = true;
}
async function load() {
  busy.value = true;
  failed.value = false;
  try {
    stats.value = (await api.overview()).data;
    if (profile.value)
      recommendations.value = (await api.recommendations()).data;
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
const metrics = computed(() => [
  {
    title: "我的高考成绩",
    value: profile.value ? number(profile.value.score) : "待完善",
    unit: profile.value ? "分" : "",
    note: profile.value
      ? `全省位次 ${number(profile.value.rank)}`
      : "完善画像，开启规划",
    icon: ContactRound,
    color: "blue",
    link: "/profile",
  },
  {
    title: "匹配专业组",
    value: recommendations.value.items.length,
    unit: "个",
    note: `从 ${stats.value.universities} 所模拟院校中筛选`,
    icon: School,
    color: "purple",
    link: "/analysis",
  },
  {
    title: "当前志愿草稿",
    value: planner.items.length,
    unit: "个",
    note: "按冲 · 稳 · 保合理配置",
    icon: Route,
    color: "orange",
    link: "/planner",
  },
  {
    title: "已保存方案",
    value: stats.value.plans,
    unit: "份",
    note: "随时对比，找到更优选择",
    icon: FolderHeart,
    color: "green",
    link: "/plans",
  },
]);
</script>
<template>
  <div class="dashboard" v-loading="busy">
    <div class="page-heading">
      <div>
        <div class="eyebrow">YOUR FUTURE STARTS HERE</div>
        <h1>
          {{ auth.user?.name }}，向理想更近一步<span class="heading-sun"
            >✳</span
          >
        </h1>
        <p>每一次认真选择，都在为未来铺路。一起找到适合你的方向。</p>
      </div>
      <RouterLink to="/profile" class="profile-pill"
        ><span class="status-dot"></span
        >{{
          profile
            ? `${profile.province} · ${profile.exam_year}届 · ${profile.subjects.join(" / ")}`
            : "完善我的考生画像"
        }}<ChevronRight :size="14"
      /></RouterLink>
    </div>
    <div v-if="failed" class="notice">
      工作台加载失败。<button class="text-button" @click="load">
        重新加载
      </button>
    </div>
    <section class="hero-banner">
      <div class="hero-copy">
        <div class="hero-label">
          <Sparkles :size="14" />让数据指路，让选择有底气
        </div>
        <h2>你的下一站，<span>不止一种可能。</span></h2>
        <p>
          基于考生画像与历年位次，发现适合你的院校与专业。<br />从心之所向，到行之有方。
        </p>
        <button
          class="hero-button"
          @click="router.push(profile ? '/analysis' : '/profile')"
        >
          {{ profile ? "开启智能匹配" : "完善画像，开启规划"
          }}<ArrowRight :size="17" /></button
        ><span class="hero-footnote">规则驱动分析 · 可解释的冲稳保建议</span>
      </div>
      <div class="hero-art" aria-hidden="true">
        <div class="hero-orbit orbit-a"></div>
        <div class="hero-orbit orbit-b"></div>
        <div class="hero-orbit orbit-c"></div>
        <div class="hero-sun"></div>
        <div class="hero-horizon"></div>
        <span class="hero-star star-a">✦</span
        ><span class="hero-star star-b">✦</span>
        <div class="destination">
          <Compass :size="15" /><span>奔赴你的理想</span
          ><ArrowUpRight :size="14" />
        </div>
        <span class="hero-art-caption">THE FUTURE IS YOURS TO EXPLORE</span>
      </div>
    </section>
    <section class="metric-grid">
      <RouterLink
        v-for="metric in metrics"
        :key="metric.title"
        :to="metric.link"
        class="metric-card"
        ><div class="metric-top">
          <span>{{ metric.title }}</span
          ><span :class="['metric-icon', metric.color]"
            ><component :is="metric.icon" :size="18"
          /></span>
        </div>
        <div class="metric-value">
          {{ metric.value }}<small>{{ metric.unit }}</small>
        </div>
        <div class="metric-note">
          {{ metric.note }}<ArrowUpRight :size="14" /></div
      ></RouterLink>
    </section>
    <div class="dashboard-middle">
      <section class="panel trend-panel">
        <div class="section-heading">
          <div>
            <h3>录取位次趋势<span class="tag subtle">近三年</span></h3>
            <p>与你匹配的代表院校，看看往年的选择轨迹</p>
          </div>
          <RouterLink to="/analysis" class="text-button muted"
            ><SlidersHorizontal :size="14" />更多分析</RouterLink
          >
        </div>
        <TrendChart
          v-if="featured.length"
          :groups="featured"
          :student-rank="profile?.rank"
          :height="240"
        />
        <div v-else class="chart-empty">
          <Compass :size="30" />
          <p>
            {{
              profile
                ? "当前画像暂无可匹配院校，可调整画像或查看招生数据"
                : "完善考生画像后，解锁专属位次分析"
            }}
          </p>
          <RouterLink to="/profile" class="text-button"
            >完善画像 <ArrowRight :size="14"
          /></RouterLink>
        </div>
        <div class="chart-caption">
          <Info :size="13" />位次数值越小，排名越靠前 · 数据为模拟样本
        </div>
      </section>
      <section class="panel journey-panel">
        <div class="section-heading">
          <div>
            <h3>我的规划进度</h3>
            <p>把大选择，拆成每一个小步骤</p>
          </div>
          <span class="journey-progress"
            >{{ progress }}<small> / 3</small></span
          >
        </div>
        <div class="journey-steps">
          <RouterLink to="/profile" class="journey-step"
            ><span :class="['step-num', { complete: profile }]"
              ><Check v-if="profile" :size="15" /><template v-else
                >1</template
              ></span
            >
            <div>
              <strong>了解自己，完善画像</strong>
              <p>
                {{
                  profile
                    ? "已完成，好的选择从了解自己开始"
                    : "填写成绩、位次与兴趣偏好"
                }}
              </p>
            </div>
            <ChevronRight :size="16" /></RouterLink
          ><RouterLink to="/analysis" class="journey-step"
            ><span
              :class="[
                'step-num',
                { complete: progress >= 2, current: progress === 1 },
              ]"
              ><Check v-if="progress >= 2" :size="15" /><template v-else
                >2</template
              ></span
            >
            <div>
              <strong>探索院校，智能匹配</strong>
              <p>找到冲、稳、保的合理组合</p>
            </div>
            <ChevronRight :size="16" /></RouterLink
          ><RouterLink to="/planner" class="journey-step"
            ><span :class="['step-num', { complete: stats.plans }]"
              ><Check v-if="stats.plans" :size="15" /><template v-else
                >3</template
              ></span
            >
            <div>
              <strong>调整顺序，保存方案</strong>
              <p>反复推敲，让每个志愿更有把握</p>
            </div>
            <ChevronRight :size="16"
          /></RouterLink>
        </div>
        <RouterLink to="/planner" class="journey-link"
          >继续我的志愿规划<ArrowRight :size="15"
        /></RouterLink>
      </section>
    </div>
    <section class="recommended-section">
      <div class="section-heading">
        <div>
          <h3>为你发现的院校<span class="tag warm">专属推荐</span></h3>
          <p>结合位次与兴趣偏好，让每个选择都有依据</p>
        </div>
        <RouterLink to="/analysis" class="text-button"
          >查看全部匹配 <ArrowRight :size="15"
        /></RouterLink>
      </div>
      <div v-if="featured.length" class="school-grid">
        <SchoolCard
          v-for="group in featured"
          :key="group.id"
          :group="group"
          @detail="show"
        />
      </div>
      <el-empty
        v-else
        :description="
          profile
            ? '暂无符合条件的模拟推荐'
            : '先完善考生画像，再发现适合你的大学'
        "
        ><el-button @click="router.push('/profile')"
          >完善考生画像</el-button
        ></el-empty
      >
    </section>
    <div class="data-disclaimer">
      <Info :size="15" /><span
        >理性参考，认真选择：本站招生数据均为模拟样本，冲稳保为规则估算，不代表实际录取概率。正式填报以官方公布为准。</span
      >
    </div>
    <GroupDrawer v-model="drawer" :group="detail" />
  </div>
</template>
