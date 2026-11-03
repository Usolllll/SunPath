import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { useAuth } from "./auth";
import { ElMessage } from "element-plus/es/components/message/index";
import type { Group } from "../api/types";

export const usePlanner = defineStore("planner", () => {
  const auth = useAuth();
  const items = ref<Group[]>([]);
  const editingId = ref<number | undefined>();
  const name = ref("我的志愿方案");
  const profileKey = ref("");
  const key = () => `sunpath.draft.${auth.user?.id}`;
  function restore() {
    try {
      const data = JSON.parse(localStorage.getItem(key()) || "{}");
      items.value = Array.isArray(data.items) ? data.items : [];
      editingId.value = data.editingId;
      name.value = data.name || "我的志愿方案";
      profileKey.value = data.profileKey || "";
    } catch {
      items.value = [];
      editingId.value = undefined;
      profileKey.value = "";
      name.value = "我的志愿方案";
    }
  }
  watch(() => auth.user?.id, restore, { immediate: true });
  watch(
    [items, editingId, name, profileKey],
    () => {
      if (auth.user)
        localStorage.setItem(
          key(),
          JSON.stringify({
            items: items.value,
            editingId: editingId.value,
            name: name.value,
            profileKey: profileKey.value,
          }),
        );
    },
    { deep: true, flush: "sync" },
  );
  function add(group: Group) {
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
  ) {
    items.value = groups;
    editingId.value = id;
    name.value = planName;
    profileKey.value = JSON.stringify(snapshot);
  }
  function move(index: number, delta: number) {
    const next = index + delta;
    if (next < 0 || next >= items.value.length) return;
    const copy = [...items.value];
    [copy[index], copy[next]] = [copy[next]!, copy[index]!];
    items.value = copy;
  }
  return { items, editingId, name, profileKey, add, replace, move };
});
