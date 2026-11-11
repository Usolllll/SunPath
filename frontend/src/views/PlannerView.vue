<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  ArrowUp,
  ArrowDown,
  Trash2,
  Plus,
  Save,
  ArrowRight,
  Info,
  GripVertical,
  Download,
  FilePlus2,
  Wallet,
  Send,
  Undo2,
  Lock,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import { useRouter } from "vue-router";
import { usePlanner } from "../stores/planner";
import { useAuth } from "../stores/auth";
import { api } from "../api";
import { number, riskLabels, exportPlan, date } from "../utils/format";
import { overBudgetText, wan } from "../utils/decision";
import {
  PLAN_BATCHES,
  SUBMIT_LOCK_MESSAGE,
  clearedSubmitKey,
  idempotencySignature,
  isPlanEditable,
  isValidSubmitKey,
  planStatusLabel,
  submitKeyFor,
  type SubmitKeyState,
} from "../utils/rtm";
import RiskBadge from "../components/RiskBadge.vue";
import GroupDrawer from "../components/GroupDrawer.vue";
import type { Group } from "../api/types";
const planner = usePlanner();
const auth = useAuth();
const router = useRouter();
const saving = ref(false);
const saveAs = ref(false);
const saveDialog = ref(false);
const exporting = ref(false);
const costing = ref(false);
const submitting = ref(false);
const withdrawing = ref(false);
const syncing = ref(false);
const detail = ref<Group | null>(null);
const drawer = ref(false);
// RTM：草稿可编辑；已提交需先撤回，提交请求复用同一 Idempotency-Key
const editable = computed(() => isPlanEditable(planner.status));
const statusText = computed(() => planStatusLabel(planner.status));
const submittedText = computed(() =>
  planner.submittedAt ? date(planner.submittedAt) : "未记录",
);
let submitKeyState: SubmitKeyState = clearedSubmitKey();
const counts = computed(() =>
  Object.fromEntries(
    Object.keys(riskLabels).map((r) => [
      r,
      planner.items.filter((g) => g.risk === r).length,
    ]),
  ),
);
// v2：方案四年总成本（估算）+ 超预算项提示
const budget = computed(() => auth.user?.profile?.budget_total ?? null);
const totalCost = computed(() =>
  planner.items.reduce((sum, item) => sum + (item.cost?.total ?? 0), 0),
);
const pricedCount = computed(
  () => planner.items.filter((item) => item.cost?.total != null).length,
);
const missingCount = computed(() => planner.items.length - pricedCount.value);
const overItems = computed(() =>
  planner.items.filter(
    (item) =>
      item.cost?.total != null &&
      budget.value != null &&
      item.cost.total > budget.value,
  ).length,
);
function itemOverText(item: Group): string | null {
  return overBudgetText(item.cost?.total ?? null, budget.value);
}
/** 旧版保存的方案可能没有 cost 字段：按专业组补拉一次四年成本估算 */
async function ensureCosts() {
  const missing = planner.items
    .filter((item) => item.cost?.total == null)
    .slice(0, 30);
  if (!missing.length) return;
  costing.value = true;
  await Promise.all(
    missing.map(async (item) => {
      try {
        const { data } = await api.budgetEstimate(item.id);
        const index = planner.items.findIndex((x) => x.id === item.id);
        if (index >= 0)
          planner.items[index] = { ...planner.items[index], cost: data.cost };
      } catch {
        /* 拉取失败时保留“未收录” */
      }
    }),
  );
  costing.value = false;
}
watch(
  () => planner.items.map((item) => item.id).join(","),
  () => void ensureCosts(),
);
/** 已保存方案在其它页面提交/撤回后，进入本页时同步一次状态 */
async function syncPlanState() {
  if (!planner.editingId) return;
  syncing.value = true;
  try {
    const plans = (await api.plans()).data;
    const current = plans.find((plan) => plan.id === planner.editingId);
    if (current) planner.applyLifecycle(current);
  } catch {
    /* 同步失败时保留本机状态，不打断编辑 */
  } finally {
    syncing.value = false;
  }
}
onMounted(() => {
  void ensureCosts();
  void syncPlanState();
});

const stale = computed(
  () =>
    planner.items.length &&
    planner.profileKey !== JSON.stringify(auth.user?.profile),
);
function show(g: Group) {
  detail.value = g;
  drawer.value = true;
}
function errorStatus(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status;
}
function planSignature(): string {
  return idempotencySignature({
    planId: planner.editingId,
    name: planner.name,
    batch: planner.batch,
    itemIds: planner.items.map((item) => item.id),
  });
}
async function save() {
  if (saving.value) return;
  if (!editable.value && !saveAs.value)
    return ElMessage.warning(SUBMIT_LOCK_MESSAGE);
  if (!planner.name.trim()) return ElMessage.warning("请输入方案名称");
  saving.value = true;
  try {
    const response = await api.savePlan(
      planner.name,
      planner.items.map((g) => g.id),
      saveAs.value ? undefined : planner.editingId,
      planner.batch,
    );
    planner.editingId = response.data.id;
    planner.name = response.data.name;
    planner.profileKey = JSON.stringify(auth.user?.profile);
    planner.applyLifecycle(response.data);
    saveDialog.value = false;
    ElMessage.success(
      saveAs.value
        ? "已另存为新方案，可在“我的志愿方案”中查看"
        : "志愿方案已保存，可在“我的志愿方案”中查看与对比",
    );
    saveAs.value = false;
  } catch (error) {
    if (errorStatus(error) === 409) ElMessage.warning(SUBMIT_LOCK_MESSAGE);
    /* 其它错误由 axios 拦截器提示 */
  } finally {
    saving.value = false;
  }
}
/** 提交方案：已提交后不可编辑；请求复用同一 Idempotency-Key，成功后清空 */
async function submitPlan() {
  if (submitting.value || withdrawing.value) return;
  if (!editable.value) return ElMessage.warning(SUBMIT_LOCK_MESSAGE);
  if (!planner.items.length)
    return ElMessage.warning("当前方案还没有志愿，无法提交");
  if (stale.value)
    return ElMessage.warning("考生画像已变更，请先重新匹配并保存方案后再提交");
  if (!planner.editingId)
    return ElMessage.warning("请先保存方案，再提交给系统记录");
  try {
    await ElMessageBox.confirm(
      `提交后方案将不可编辑（${planner.batch}），如需修改需先撤回。确定提交“${planner.name}”？`,
      "提交志愿方案",
      { confirmButtonText: "确认提交", cancelButtonText: "再想想" },
    );
  } catch {
    return;
  }
  submitting.value = true;
  try {
    // 提交前先保存当前草稿，保证服务端提交内容与屏幕上的顺序/志愿一致
    const saved = await api.savePlan(
      planner.name,
      planner.items.map((item) => item.id),
      planner.editingId,
      planner.batch,
    );
    planner.editingId = saved.data.id;
    planner.name = saved.data.name;
    planner.profileKey = JSON.stringify(auth.user?.profile);
    planner.applyLifecycle(saved.data);
    submitKeyState = submitKeyFor(planSignature(), submitKeyState, () =>
      crypto.randomUUID(),
    );
    if (!isValidSubmitKey(submitKeyState.key)) {
      submitKeyState = clearedSubmitKey();
      return ElMessage.error("提交请求 key 生成失败，请重试");
    }
    const { data } = await api.submitPlan(planner.editingId, submitKeyState.key);
    planner.applyLifecycle(data);
    submitKeyState = clearedSubmitKey();
    ElMessage.success("方案已提交；已提交方案不可编辑，需要修改请先撤回");
  } catch (error) {
    if (errorStatus(error) === 409) ElMessage.warning(SUBMIT_LOCK_MESSAGE);
    else if (!errorStatus(error))
      ElMessage.error("提交失败，请检查网络后重试");
    // 提交失败保留同一个 key，重试不会重复创建记录
  } finally {
    submitting.value = false;
  }
}
/** 撤回方案：回到草稿后可继续编辑 */
async function withdrawPlan() {
  if (withdrawing.value || submitting.value) return;
  if (!planner.editingId) return;
  try {
    await ElMessageBox.confirm(
      "撤回后方案回到草稿状态，可以继续编辑；已提交记录会保留撤回时间。确定撤回？",
      "撤回方案",
      { confirmButtonText: "确认撤回", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  withdrawing.value = true;
  try {
    const { data } = await api.withdrawPlan(planner.editingId);
    planner.applyLifecycle(data);
    submitKeyState = clearedSubmitKey();
    ElMessage.success("已撤回为草稿，可以继续编辑");
  } catch (error) {
    if (errorStatus(error) === 409) ElMessage.warning(SUBMIT_LOCK_MESSAGE);
  } finally {
    withdrawing.value = false;
  }
}
async function clear() {
  if (!editable.value) return ElMessage.warning(SUBMIT_LOCK_MESSAGE);
  try {
    await ElMessageBox.confirm(
      "清空当前草稿？已保存的历史方案仍会保留。",
      "新建方案",
      { confirmButtonText: "清空并新建", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  planner.reset();
  submitKeyState = clearedSubmitKey();
}
async function download() {
  if (!planner.editingId) return;
  exporting.value = true;
  try {
    await exportPlan(planner.editingId);
    ElMessage.success("已导出最后保存的方案版本");
  } catch {
    /* API handles error */
  } finally {
    exporting.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">MAKE YOUR NEXT MOVE COUNT</div>
      <h1>把心中的方向，排成未来的模样</h1>
      <p>合理搭配冲稳保梯度，反复推敲每一个志愿。</p>
    </div>
    <div class="heading-actions">
      <el-select
        v-model="planner.batch"
        class="batch-select"
        :disabled="!editable"
        aria-label="方案批次"
      >
        <el-option
          v-for="batch in PLAN_BATCHES"
          :key="batch"
          :value="batch"
          :label="batch"
        />
      </el-select>
      <el-button :disabled="!editable" @click="clear"
        ><FilePlus2 :size="16" />新建方案</el-button
      ><el-button
        type="primary"
        size="large"
        :disabled="!planner.items.length || !!stale || !editable"
        @click="
          saveAs = false;
          saveDialog = true;
        "
        ><Save :size="16" />保存方案</el-button
      >
    </div>
  </div>
  <div v-if="stale" class="notice">
    考生画像已变更，当前草稿可能包含不符合新画像的专业组。请前往智能匹配重新生成，或重新添加最新匹配结果。<RouterLink
      to="/analysis"
      class="text-button"
      >重新匹配<ArrowRight :size="14"
    /></RouterLink>
  </div>
  <div v-if="!editable" class="notice compact plan-locked-notice">
    <Lock :size="14" />已提交的方案不可编辑（提交于 {{ submittedText }}，批次
    {{ planner.batch }}）。如需修改，请先「撤回为草稿」。
  </div>
  <template v-if="planner.items.length"
    ><div class="planner-layout">
      <section class="panel planner-table">
        <div class="section-heading">
          <div>
            <h3>
              {{ planner.name
              }}<span
                class="tag"
                :class="planner.status === 'submitted' ? 'warm' : 'subtle'"
                >{{ statusText }}</span
              ><span class="tag subtle">{{ planner.batch }}</span>
            </h3>
            <p>
              共 {{ planner.items.length }} 个专业组 ·
              {{
                editable
                  ? "使用上下箭头调整优先顺序"
                  : "已提交，顺序与志愿均锁定"
              }}
            </p>
          </div>
          <RouterLink v-if="editable" to="/analysis" class="text-button"
            ><Plus :size="15" />添加志愿</RouterLink
          ><span v-else class="text-button muted locked-hint"
            ><Lock :size="14" />已提交锁定</span
          >
        </div>
        <div
          v-for="(item, index) in planner.items"
          :key="item.id"
          class="planner-row"
        >
          <div class="planner-order">
            <GripVertical :size="14" /><strong>{{
              String(index + 1).padStart(2, "0")
            }}</strong>
          </div>
          <button class="planner-school" @click="show(item)">
            <h3>
              {{ item.university.name }}<RiskBadge :risk="item.risk" short />
            </h3>
            <p>{{ item.name }} · {{ item.majors.slice(0, 2).join(" / ") }}</p>
            <span
              >{{ item.university.city }} ·
              {{ item.required_subjects.join(" + ") || "不限选科" }}</span
            >
          </button>
          <div class="planner-reference">
            <span>加权参考位次</span
            ><strong>{{ number(item.baseline_rank) }}</strong>
          </div>
          <div
            :class="['planner-cost', { over: itemOverText(item) }]"
            :title="item.cost?.note || '四年成本未收录'"
          >
            <span>四年约</span>
            <strong>{{ wan(item.cost?.total) }}</strong>
            <em v-if="itemOverText(item)">{{ itemOverText(item) }}</em>
          </div>
          <div class="planner-row-actions">
            <button
              class="icon-button"
              :disabled="!editable || index === 0"
              :aria-label="editable ? '上移志愿' : '已提交，不可调整顺序'"
              @click="planner.move(index, -1)"
            >
              <ArrowUp :size="16" /></button
            ><button
              class="icon-button"
              :disabled="!editable || index === planner.items.length - 1"
              :aria-label="editable ? '下移志愿' : '已提交，不可调整顺序'"
              @click="planner.move(index, 1)"
            >
              <ArrowDown :size="16" /></button
            ><button
              class="icon-button danger"
              :disabled="!editable"
              :aria-label="editable ? '删除志愿' : '已提交，不可删除志愿'"
              @click="editable && planner.items.splice(index, 1)"
            >
              <Trash2 :size="16" />
            </button>
          </div>
        </div>
        <RouterLink v-if="editable" to="/analysis" class="add-plan-row"
          ><Plus :size="16" />继续添加适合我的院校</RouterLink
        ><span v-else class="add-plan-row disabled locked-hint"
          ><Lock :size="14" />已提交方案不可编辑，撤回后可继续添加</span
        >
      </section>
      <aside>
        <section class="panel plan-summary">
          <h3>方案梯度分析</h3>
          <p class="muted">让期待与把握，保持平衡</p>
          <div class="tier-bar">
            <span
              v-for="(label, risk) in riskLabels"
              :key="risk"
              :class="risk"
              :style="{ flex: counts[risk] || 0 }"
            ></span>
          </div>
          <div
            v-for="(label, risk) in riskLabels"
            :key="risk"
            class="tier-summary"
          >
            <RiskBadge :risk="risk" /><strong
              >{{ counts[risk] }} <small>个专业组</small></strong
            >
          </div>
          <div v-loading="costing" class="plan-cost-block">
            <div class="plan-cost-head">
              <span class="plan-cost-title"
                ><Wallet :size="15" />方案四年成本合计（估算）</span
              >
              <span class="tag subtle">各志愿成本之和</span>
            </div>
            <div class="plan-cost-value">
              <strong>{{ wan(totalCost) }}</strong
              ><small>约</small>
            </div>
            <div v-if="budget" class="plan-cost-budget">
              家庭预算 {{ wan(budget) }} ·
              <strong v-if="overItems" class="cost-over-text"
                >{{ overItems }} / {{ planner.items.length }}
                个志愿的四年成本超出预算（单项超支见列表角标）</strong
              >
              <strong v-else class="cost-ok-text">全部在预算内</strong>
            </div>
            <div v-else class="plan-cost-budget">
              尚未设置家庭预算，可在考生画像中补充
            </div>
            <p class="plan-cost-note">
              {{ pricedCount }} / {{ planner.items.length }} 个专业组已收录成本估算<span
                v-if="missingCount"
                >，{{ missingCount }} 个未收录</span
              >；合计为各志愿四年成本之和，只用于横向比较预算压力，不代表实际支出。学费
              / 住宿费来自采集字段，生活费按城市等级估算，非官方数据。
            </p>
          </div>
          <div class="plan-cost-warning">
            <Info :size="14" />排序 ≠ 录取，数据为模拟 / 估算：模式与成本只用于同梯度内取舍，不代表录取结果。
          </div>
          <div class="summary-note">
            <Info :size="15" />
            <p v-if="!counts.safe">
              当前缺少保底专业组，建议补充更稳健的选择。
            </p>
            <p v-else-if="!counts.reach || !counts.steady">
              当前方案梯度不完整，可继续探索其他层次的专业组。
            </p>
            <p v-else>
              已覆盖冲稳保三个梯度。请结合专业兴趣和官方招生要求继续调整。
            </p>
          </div>
          <el-button
            type="primary"
            size="large"
            :disabled="!!stale || !editable || saving"
            @click="
              saveAs = false;
              saveDialog = true;
            "
            ><Save :size="16" />{{
              planner.editingId ? "更新保存方案" : "保存我的方案"
            }}</el-button
          ><el-button
            v-if="editable"
            type="primary"
            size="large"
            plain
            :loading="submitting"
            :disabled="
              !planner.editingId || !planner.items.length || !!stale || saving
            "
            @click="submitPlan"
            ><Send :size="16" />提交方案</el-button
          ><el-button
            v-else
            type="warning"
            size="large"
            plain
            :loading="withdrawing"
            @click="withdrawPlan"
            ><Undo2 :size="16" />撤回为草稿</el-button
          ><el-button
            v-if="planner.editingId"
            :disabled="!!stale || saving"
            @click="
              saveAs = true;
              saveDialog = true;
            "
            >另存为新方案</el-button
          ><el-button
            v-if="planner.editingId"
            :loading="exporting"
            @click="download"
            ><Download :size="15" />导出已保存版本</el-button
          ><p v-if="editable && !planner.editingId" class="plan-submit-hint">
            <Info :size="12" />提交前请先「保存方案」。
          </p>
          <p v-else-if="!editable" class="plan-submit-hint">
            <Lock :size="12" />已提交方案不可编辑；撤回后可继续调整顺序与志愿。
          </p>
          <RouterLink to="/plans" class="text-button"
            >查看历史方案与对比<ArrowRight :size="14"
          /></RouterLink>
        </section>
        <div class="notice">
          <strong>顺序，也是选择的一部分</strong>
          <p>
            草稿自动保留在本机，点击保存后才写入账号。导出内容以最后保存版本为准。
          </p>
          <p>
            本原型不校验各省正式志愿数量、批次和投档规则，方案仅作模拟演示。
          </p>
        </div>
      </aside>
    </div></template
  ><el-empty v-else description="你的志愿清单，等待第一份期待"
    ><el-button type="primary" size="large" @click="router.push('/analysis')"
      >智能匹配并生成方案<ArrowRight :size="16" /></el-button></el-empty
  ><el-dialog
    v-model="saveDialog"
    :title="saveAs ? '另存为新方案' : '保存志愿方案'"
    width="min(460px, 92vw)"
    ><label class="field-label">给方案起个名字</label
    ><el-input
      v-model="planner.name"
      maxlength="80"
      show-word-limit
      :disabled="!editable && !saveAs"
      placeholder="例如：长三角 · 计算机优先"
      @keyup.enter="save"
    />
    <p class="muted">
      批次：{{ planner.batch }} · 状态：{{ statusText }} ·
      将保存 {{ planner.items.length }} 个专业组及当前考生画像快照。
    </p>
    <template #footer
      ><el-button @click="saveDialog = false">取消</el-button
      ><el-button
        type="primary"
        :loading="saving"
        :disabled="!editable && !saveAs"
        @click="save"
        >确认保存</el-button
      ></template
    ></el-dialog
  ><GroupDrawer v-model="drawer" :group="detail" />
</template>

<style scoped>
.batch-select {
  width: 104px;
}
.batch-select :deep(.el-select__wrapper) {
  min-height: 32px;
  font-size: 11px;
}
.plan-locked-notice {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 14px;
  border-color: #e6dcc8;
  background: #fdf9f1;
  color: #93794f;
}
.locked-hint {
  color: #9aa8ba;
  cursor: default;
}
.add-plan-row.disabled {
  cursor: default;
  color: #a4afbd;
}
.plan-submit-hint {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  color: #9aa8ba;
  margin-top: -4px;
  line-height: 1.7;
}
</style>
