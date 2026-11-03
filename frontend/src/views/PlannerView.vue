<script setup lang="ts">
import { computed, ref } from "vue";
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
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import { useRouter } from "vue-router";
import { usePlanner } from "../stores/planner";
import { useAuth } from "../stores/auth";
import { api } from "../api";
import { number, riskLabels, exportPlan } from "../utils/format";
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
const detail = ref<Group | null>(null);
const drawer = ref(false);
const counts = computed(() =>
  Object.fromEntries(
    Object.keys(riskLabels).map((r) => [
      r,
      planner.items.filter((g) => g.risk === r).length,
    ]),
  ),
);
const stale = computed(
  () =>
    planner.items.length &&
    planner.profileKey !== JSON.stringify(auth.user?.profile),
);
function show(g: Group) {
  detail.value = g;
  drawer.value = true;
}
async function save() {
  if (saving.value) return;
  if (!planner.name.trim()) return ElMessage.warning("请输入方案名称");
  saving.value = true;
  try {
    const response = await api.savePlan(
      planner.name,
      planner.items.map((g) => g.id),
      saveAs.value ? undefined : planner.editingId,
    );
    planner.editingId = response.data.id;
    planner.name = response.data.name;
    planner.profileKey = JSON.stringify(auth.user?.profile);
    saveDialog.value = false;
    ElMessage.success("志愿方案已保存，可在“我的志愿方案”中查看与对比");
  } catch {
    /* API handles error */
  } finally {
    saving.value = false;
  }
}
async function clear() {
  try {
    await ElMessageBox.confirm(
      "清空当前草稿？已保存的历史方案仍会保留。",
      "新建方案",
      { confirmButtonText: "清空并新建", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  planner.replace([]);
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
      <el-button @click="clear"><FilePlus2 :size="16" />新建方案</el-button
      ><el-button
        type="primary"
        size="large"
        :disabled="!planner.items.length || !!stale"
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
  <template v-if="planner.items.length"
    ><div class="planner-layout">
      <section class="panel planner-table">
        <div class="section-heading">
          <div>
            <h3>
              {{ planner.name
              }}<span class="tag subtle">{{
                planner.editingId ? "编辑已存方案" : "本机草稿"
              }}</span>
            </h3>
            <p>
              共 {{ planner.items.length }} 个专业组 · 使用上下箭头调整优先顺序
            </p>
          </div>
          <RouterLink to="/analysis" class="text-button"
            ><Plus :size="15" />添加志愿</RouterLink
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
          <div class="planner-row-actions">
            <button
              class="icon-button"
              :disabled="index === 0"
              aria-label="上移志愿"
              @click="planner.move(index, -1)"
            >
              <ArrowUp :size="16" /></button
            ><button
              class="icon-button"
              :disabled="index === planner.items.length - 1"
              aria-label="下移志愿"
              @click="planner.move(index, 1)"
            >
              <ArrowDown :size="16" /></button
            ><button
              class="icon-button danger"
              aria-label="删除志愿"
              @click="planner.items.splice(index, 1)"
            >
              <Trash2 :size="16" />
            </button>
          </div>
        </div>
        <RouterLink to="/analysis" class="add-plan-row"
          ><Plus :size="16" />继续添加适合我的院校</RouterLink
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
            :disabled="!!stale"
            @click="
              saveAs = false;
              saveDialog = true;
            "
            ><Save :size="16" />{{
              planner.editingId ? "更新保存方案" : "保存我的方案"
            }}</el-button
          ><el-button
            v-if="planner.editingId"
            :disabled="!!stale"
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
          ><RouterLink to="/plans" class="text-button"
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
      placeholder="例如：长三角 · 计算机优先"
      @keyup.enter="save"
    />
    <p class="muted">
      将保存 {{ planner.items.length }} 个专业组及当前考生画像快照。
    </p>
    <template #footer
      ><el-button @click="saveDialog = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="save"
        >确认保存</el-button
      ></template
    ></el-dialog
  ><GroupDrawer v-model="drawer" :group="detail" />
</template>
