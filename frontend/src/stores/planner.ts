import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { useAuth } from "./auth";
import { ElMessage } from "element-plus/es/components/message/index";
import type { Group, PlanBatch, PlanStatus } from "../api/types";
import { SUBMIT_LOCK_MESSAGE, planBatchLabel } from "../utils/rtm";

export const usePlanner = defineStore("planner", () => {
  const auth = useAuth();
  const items = ref<Group[]>([]);
  const editingId = ref<number | undefined>();
  const name = ref("我的志愿方案");
  const profileKey = ref("");
  /** RTM：方案批次与生命周期状态（草稿可编辑 / 已提交需先撤回） */
  const batch = ref<PlanBatch>("本科批");
  const status = ref<PlanStatus>("draft");
  const submittedAt = ref<string | null>(null);
  const key = () => `sunpath.draft.${auth.user?.id}`;
  function restore() {
    try {
      const data = JSON.parse(localStorage.getItem(key()) || "{}");
      items.value = Array.isArray(data.items) ? data.items : [];
      editingId.value = data.editingId;
      name.value = data.name || "我的志愿方案";
      profileKey.value = data.profileKey || "";
      batch.value = planBatchLabel(data.batch);
      status.value = data.status === "submitted" ? "submitted" : "draft";
      submittedAt.value =
        typeof data.submittedAt === "string" ? data.submittedAt : null;
    } catch {
      items.value = [];
      editingId.value = undefined;
      profileKey.value = "";
      name.value = "我的志愿方案";
      batch.value = "本科批";
      status.value = "draft";
      submittedAt.value = null;
    }
  }
  watch(() => auth.user?.id, restore, { immediate: true });
  watch(
    [items, editingId, name, profileKey, batch, status, submittedAt],
    () => {
      if (auth.user)
        localStorage.setItem(
          key(),
          JSON.stringify({
            items: items.value,
            editingId: editingId.value,
            name: name.value,
            profileKey: profileKey.value,
            batch: batch.value,
            status: status.value,
            submittedAt: submittedAt.value,
          }),
        );
    },
    { deep: true, flush: "sync" },
  );
  function add(group: Group) {
    if (status.value === "submitted")
      return ElMessage.warning(SUBMIT_LOCK_MESSAGE);
    if (items.value.some((x) => x.id === group.id))
      return ElMessage.info("该专业组已在方案中");
    if (items.value.length >= 30)
      return ElMessage.warning("MVP 每个方案最多 30 个专业组");
    if (!group.risk)
      return ElMessage.warning(
        "请先前往智能匹配，查看该专业组是否符合你的画像",
      );
    if (!items.value.length)
      profileKey.value = JSON.stringify(auth.user?.profile);
    items.value.push(group);
    ElMessage.success("已加入志愿草稿");
  }
  function replace(
    groups: Group[],
    id?: number,
    planName = "我的志愿方案",
    snapshot = auth.user?.profile,
    lifecycle: {
      batch?: PlanBatch | null;
      status?: PlanStatus | null;
      submittedAt?: string | null;
    } = {},
  ) {
    items.value = groups;
    editingId.value = id;
    name.value = planName;
    profileKey.value = JSON.stringify(snapshot);
    batch.value = planBatchLabel(lifecycle.batch);
    status.value = lifecycle.status === "submitted" ? "submitted" : "draft";
    submittedAt.value = lifecycle.submittedAt ?? null;
  }
  function move(index: number, delta: number) {
    if (status.value === "submitted") {
      ElMessage.warning(SUBMIT_LOCK_MESSAGE);
      return;
    }
    const next = index + delta;
    if (next < 0 || next >= items.value.length) return;
    const copy = [...items.value];
    [copy[index], copy[next]] = [copy[next]!, copy[index]!];
    items.value = copy;
  }
  /** 清空为一份新的本地草稿（批次回到默认值，状态回到 draft） */
  function reset() {
    items.value = [];
    editingId.value = undefined;
    name.value = "我的志愿方案";
    profileKey.value = "";
    batch.value = "本科批";
    status.value = "draft";
    submittedAt.value = null;
  }
  /** 保存 / 提交 / 撤回后同步服务端返回的生命周期字段 */
  function applyLifecycle(next: {
    batch?: PlanBatch | null;
    status?: PlanStatus | null;
    submitted_at?: string | null;
  }) {
    batch.value = planBatchLabel(next.batch);
    status.value = next.status === "submitted" ? "submitted" : "draft";
    submittedAt.value = next.submitted_at ?? null;
  }
  return {
    items,
    editingId,
    name,
    profileKey,
    batch,
    status,
    submittedAt,
    add,
    replace,
    move,
    reset,
    applyLifecycle,
  };
});
