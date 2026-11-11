<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  AlertTriangle,
  BookOpen,
  Heart,
  Info,
  Repeat2,
  ShieldCheck,
} from "lucide-vue-next";
import type { BudgetEstimate, Group } from "../api/types";
import TrendChart from "./TrendChart.vue";
import RiskBadge from "./RiskBadge.vue";
import MajorCardDrawer from "./MajorCardDrawer.vue";
import ReadinessList from "./ReadinessList.vue";
import { usePlanner } from "../stores/planner";
import { useAuth } from "../stores/auth";
import { useFavorites } from "../stores/favorites";
import { number } from "../utils/format";
import {
  cityTierLabel,
  levelTierLabel,
  overBudgetText,
  transferStars,
  wan,
  yuan,
} from "../utils/decision";
import { api } from "../api";
import { officialCheckText, safeSourceUrl } from "../utils/realdata";
const props = defineProps<{ group: Group | null }>();
const open = defineModel<boolean>({ required: true });
const planner = usePlanner();
const auth = useAuth();
const estimate = ref<BudgetEstimate | null>(null);
const estimateLoading = ref(false);
const majorOpen = ref(false);
const majorName = ref<string | null>(null);
const budget = computed(() => auth.user?.profile?.budget_total ?? null);
const cost = computed(() => estimate.value?.cost ?? props.group?.cost ?? null);
const costTotal = computed(() => cost.value?.total ?? null);
const overText = computed(() => overBudgetText(costTotal.value, budget.value));
const overBy = computed(() => {
  if (estimate.value) return estimate.value.over_by;
  if (costTotal.value == null || budget.value == null) return 0;
  return Math.max(0, costTotal.value - budget.value);
});
const transfer = computed(() =>
  transferStars(props.group?.university.transfer_friendly),
);
/** 官方真实投档核对；official 为 null（如演示账号浙江）属正常缺数据，低调提示即可 */
const official = computed(() => props.group?.official ?? null);
const officialText = computed(() => officialCheckText(official.value));
const officialUrl = computed(() => safeSourceUrl(official.value?.source_url));
/** 收藏（真实用户行为）：由 /favorites/ids 初始化，点击乐观切换 */
const favorites = useFavorites();
const favorited = computed(() =>
  props.group ? favorites.has(props.group.university.id) : false,
);
async function toggleFavorite() {
  if (!props.group) return;
  await favorites.toggle(props.group.university.id, props.group.university.name);
}
/** RTM 体检提示：只做黄/红提示，不参与筛选，也不构成报考资格认定 */
const physicalFlags = computed(() => props.group?.physical_flags ?? []);
const tierTags = computed(() => {
  const university = props.group?.university;
  if (!university) return [];
  return [
    { label: cityTierLabel(university.city_tier), title: "城市分级参考城市商业魅力排行榜，仅用于排序参考" },
    { label: levelTierLabel(university.level_tier), title: "院校层次分由 985 / 211 / 双一流名单换算，仅用于内部排序" },
  ];
});
async function loadEstimate(groupId: number) {
  estimateLoading.value = true;
  estimate.value = null;
  try {
    estimate.value = (await api.budgetEstimate(groupId)).data;
  } catch {
    /* 成本估算失败时回退到推荐结果里的 cost 字段 */
  } finally {
    estimateLoading.value = false;
  }
}
function openMajor(name: string) {
  majorName.value = name;
  majorOpen.value = true;
}
watch(
  () => [open.value, props.group?.id] as const,
  ([isOpen, id]) => {
    if (isOpen && typeof id === "number") void loadEstimate(id);
    if (!isOpen) {
      estimate.value = null;
      majorOpen.value = false;
    }
  },
);
</script>
<template>
  <el-drawer v-model="open" title="院校与专业组分析" size="min(620px, 100%)"
    ><div v-if="group" class="detail-body">
      <div class="section-heading">
        <div>
          <h2>{{ group.university.name }}</h2>
          <p>{{ group.university.city }} · {{ group.university.level }}</p>
        </div>
        <div class="detail-heading-actions">
          <RiskBadge :risk="group.risk" />
          <button
            class="favorite-button"
            :class="{ active: favorited }"
            :aria-pressed="favorited"
            :aria-label="
              favorited
                ? `取消收藏${group.university.name}`
                : `收藏${group.university.name}`
            "
            @click="toggleFavorite"
          >
            <Heart :size="14" :fill="favorited ? 'currentColor' : 'none'" />
            <span>{{ favorited ? "已收藏" : "收藏院校" }}</span>
          </button>
        </div>
      </div>
      <div class="school-tags detail-tags">
        <span class="tag">{{ group.university.category }}</span>
        <span
          v-for="tag in tierTags"
          :key="tag.label"
          class="tag"
          :title="tag.title"
          >{{ tag.label }}</span
        >
        <span v-if="group.major_category" class="tag">{{ group.major_category }}</span>
      </div>
      <p>{{ group.university.description }}</p>
      <div class="notice compact">
        模拟数据 · {{ group.province }}生源 · {{ group.year }} 年方案参考
      </div>
      <div class="official-block" :class="{ missing: !official }">
        <div class="official-block-head">
          <ShieldCheck :size="14" />
          <strong>官方核对</strong>
          <span v-if="official" class="official-block-tag">官方投档数据</span>
          <span v-else class="official-block-tag muted">官方数据未收录</span>
        </div>
        <template v-if="official">
          <p class="official-block-line">{{ officialText }}</p>
          <p class="official-block-meta">
            投档最低分 {{ official.min_score ?? "未收录" }} · 公告发布
            {{ official.published_at || "未标注" }}
            <a
              v-if="officialUrl"
              :href="officialUrl"
              target="_blank"
              rel="noopener noreferrer"
              >来源公告 ↗</a
            >
            <span v-else class="muted">（来源链接未收录）</span>
          </p>
          <p class="official-block-note">
            真实投档线不等于录取线，不代表今年录取结果；仅作核对参考，正式填报以省考试院当年公布为准。
          </p>
        </template>
        <p v-else class="official-block-line muted">
          {{ group.province }} 的官方投档数据尚未入库，本页位次与分数参考来自模拟样本，未做任何推测。
        </p>
      </div>
      <div v-if="physicalFlags.length" class="drawer-physical">
        <h3><AlertTriangle :size="15" />体检相关提示</h3>
        <div
          v-for="flag in physicalFlags"
          :key="`${flag.level}-${flag.label}`"
          :class="['drawer-physical-item', flag.level]"
        >
          <span class="drawer-physical-tag">{{ flag.label }}</span>
          <p>{{ flag.text }}</p>
        </div>
        <p class="drawer-physical-note">
          <Info :size="12" />依据《普通高等学校招生体检工作指导意见》规则做提示，仅提示可能相关，
          不构成报考资格认定；最终以省考试院、高校招生章程与体检结论为准。
        </p>
      </div>
      <h3>
        {{ group.name }} <span class="muted">{{ group.code }}</span>
      </h3>
      <div class="major-chips">
        <button
          v-for="major in group.majors"
          :key="major"
          type="button"
          class="major-chip"
          :title="`查看 ${major} 的专业介绍卡`"
          @click="openMajor(major)"
        >
          <BookOpen :size="12" />{{ major }}<span>专业卡</span>
        </button>
      </div>
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
          <small>学费 / 年{{ group.tuition_type ? `（${group.tuition_type}）` : "" }}</small
          ><strong>{{ yuan(group.tuition) }}</strong>
        </div>
        <div>
          <small>住宿费 / 年</small
          ><strong>{{ yuan(group.accommodation) }}</strong>
        </div>
        <div>
          <small>学制</small
          ><strong>{{ group.duration_years ? `${group.duration_years} 年` : "未收录" }}</strong>
        </div>
        <div>
          <small>加权参考位次</small
          ><strong>{{ number(group.baseline_rank) }}</strong>
        </div>
      </div>
      <div v-loading="estimateLoading" class="cost-block">
        <h3>四年成本估算</h3>
        <div v-if="cost" class="detail-grid cost-grid">
          <div>
            <small>学费 / 年</small><strong>{{ yuan(cost.tuition) }}</strong>
          </div>
          <div>
            <small>住宿费 / 年</small><strong>{{ yuan(cost.accommodation) }}</strong>
          </div>
          <div>
            <small>生活费 / 年（估算）</small
            ><strong>{{ yuan(cost.living) }}</strong>
          </div>
          <div>
            <small>四年合计</small
            ><strong class="cost-total">{{ wan(cost.total) }}</strong>
          </div>
        </div>
        <p v-else class="muted">该专业组四年成本未收录。</p>
        <div v-if="cost" class="cost-status" :class="{ over: overBy > 0 }">
          <span v-if="overBy > 0"
            >超出家庭预算 {{ yuan(overBy) }}（预算 {{ wan(budget) }}，仅提示不隐藏）</span
          >
          <span v-else-if="budget">在家庭预算 {{ wan(budget) }} 内</span>
          <span v-else>尚未设置家庭预算，可在考生画像中补充</span>
          <span v-if="estimate" class="tag">{{ estimate.tier }}</span>
        </div>
        <p v-if="cost" class="cost-support">
          {{ cost.note }}；学费 / 住宿费来自采集字段，正式填报请以招生章程为准。
        </p>
      </div>
      <div class="transfer-block">
        <h3><Repeat2 :size="15" />转专业友好度</h3>
        <p v-if="transfer" class="transfer-line">
          <span class="transfer-stars">{{ transfer.stars }}</span>
          <strong>{{ transfer.label }}</strong>
          <span v-if="group.university.transfer_year" class="muted"
            >（{{ group.university.transfer_year }} 年资料）</span
          >
        </p>
        <p v-else class="transfer-line muted">
          <strong>未收录</strong>（该校转专业政策暂无收录）
        </p>
        <p v-if="group.university.transfer_notes" class="transfer-notes">
          {{ group.university.transfer_notes }}
        </p>
        <p v-else class="transfer-notes muted">
          星级来自已收录资料的粗分，仅作方向参考；实际政策请查阅学校教务处公告。
        </p>
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
      <ReadinessList :group-id="group.id" />
      <div class="notice">
        <strong>填报提示</strong>
        <p>
          {{
            group.warnings?.join("；") ||
            "模拟样本仅供原型演示。实际招生专业、选科、计划和学费请核实官方信息。"
          }}
        </p>
        <p>排序只影响梯度内的选择与顺序，不代表录取结果；成本为模拟 / 估算值。</p>
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
      <p class="detail-footnote"><Info :size="12" />缺数据统一显示“未收录”，不做推测。</p>
    </div></el-drawer
  >
  <MajorCardDrawer v-model="majorOpen" :name="majorName" />
</template>

<style scoped>
.official-block {
  margin: 14px 0 4px;
  padding: 12px 14px;
  border: 1px solid #dfeee5;
  background: #f6faf7;
  border-radius: 8px;
  font-size: 11px;
  color: #5f7d6b;
  line-height: 1.8;
}
.official-block.missing {
  border-color: #e9eef6;
  background: #f7f9fc;
  color: #93a1b3;
}
.official-block-head {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #4a7f63;
}
.official-block.missing .official-block-head {
  color: #8593a7;
}
.official-block-head strong {
  font-size: 12px;
  font-weight: 600;
}
.official-block-tag {
  font-size: 9px;
  color: #4a7f63;
  background: #e9f4ee;
  border-radius: 3px;
  padding: 1px 6px;
}
.official-block-tag.muted {
  color: #8593a7;
  background: #eff2f7;
}
.official-block-line {
  margin-top: 6px;
  color: #47664f;
  font-weight: 500;
}
.official-block.missing .official-block-line {
  color: #93a1b3;
  font-weight: 400;
}
.official-block-meta {
  margin-top: 2px;
  font-size: 10px;
  color: #8fa08f;
}
.official-block-meta a {
  color: #4f7fbe;
  margin-left: 6px;
}
.official-block-meta a:hover {
  text-decoration: underline;
}
.official-block-note {
  margin-top: 5px;
  font-size: 10px;
  color: #9aa8a0;
}
.detail-heading-actions {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.favorite-button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: #8b98aa;
  background: #f5f7fa;
  border: 1px solid #e8edf4;
  border-radius: 6px;
  padding: 6px 9px;
  transition:
    color 0.15s,
    background 0.15s;
}
.favorite-button:hover {
  color: #d06a7a;
  background: #fff2f4;
  border-color: #f3d4da;
}
.favorite-button.active {
  color: #cf5d70;
  background: #fff0f3;
  border-color: #f0ccd4;
}
.drawer-physical {
  margin: 16px 0 4px;
  border: 1px solid #f4e6c9;
  background: #fffaf1;
  border-radius: 8px;
  padding: 12px 14px;
}
.drawer-physical > h3 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 8px;
  font-size: 12px;
  color: #9c7a3f;
}
.drawer-physical-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 11px;
  line-height: 1.7;
  padding: 5px 0;
  border-top: 1px dashed #f0e3c8;
}
.drawer-physical-item:first-of-type {
  border-top: 0;
}
.drawer-physical-item p {
  color: #8a7149;
}
.drawer-physical-tag {
  flex-shrink: 0;
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}
.drawer-physical-item.red .drawer-physical-tag {
  color: #b4555f;
  background: #fdeef0;
}
.drawer-physical-item.yellow .drawer-physical-tag {
  color: #9c7a3f;
  background: #f9eed6;
}
.drawer-physical-note {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-top: 8px;
  font-size: 9px;
  color: #a5a08f;
  line-height: 1.7;
}
.drawer-physical-note > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
</style>
