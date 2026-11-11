import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import { useAuth } from "./auth";
import { hasId, toggleId } from "../utils/rtm";

/**
 * 收藏状态（真实用户行为，非模拟数据）。
 * ids 在 AppLayout 挂载时用 /favorites/ids 初始化一次，卡片按钮直接读本地状态；
 * 切换采用乐观更新：先改本地再请求，失败回滚并提示。
 */
export const useFavorites = defineStore("favorites", () => {
  const auth = useAuth();
  const ids = ref<number[]>([]);
  const loaded = ref(false);
  const loading = ref(false);
  const pending = new Set<number>();

  function has(universityId: number): boolean {
    return hasId(ids.value, universityId);
  }
  function sync(next: number[]) {
    ids.value = [...new Set(next)];
    loaded.value = true;
  }
  async function load(force = false) {
    if (!auth.token) {
      ids.value = [];
      loaded.value = false;
      return;
    }
    if (loading.value || (loaded.value && !force)) return;
    loading.value = true;
    try {
      sync((await api.favoriteIds()).data.ids ?? []);
    } catch {
      /* 收藏状态加载失败不阻塞主流程 */
    } finally {
      loading.value = false;
    }
  }
  /**
   * 乐观切换收藏；返回切换后的状态，请求被跳过或失败回滚时返回 null / 原状态。
   * 只有本地成功后才 toast，避免“页面闪一下又回滚”。
   */
  async function toggle(
    universityId: number,
    universityName?: string,
  ): Promise<boolean | null> {
    if (!auth.token) {
      ElMessage.warning("请先登录后再收藏院校");
      return null;
    }
    if (pending.has(universityId)) return null;
    pending.add(universityId);
    const wasFavorited = has(universityId);
    ids.value = toggleId(ids.value, universityId);
    try {
      if (wasFavorited) await api.removeFavorite(universityId);
      else await api.addFavorite(universityId);
      loaded.value = true;
      const suffix = universityName ? ` ${universityName}` : "";
      ElMessage.success(wasFavorited ? `已取消收藏${suffix}` : `已收藏${suffix}`);
      return !wasFavorited;
    } catch (error) {
      // 404：服务端已没有这条收藏，本地“已取消”与之一致，不用回滚
      const status = (error as { response?: { status?: number } })?.response
        ?.status;
      if (wasFavorited && status === 404) return false;
      ids.value = toggleId(ids.value, universityId);
      ElMessage.error(
        wasFavorited ? "取消收藏失败，已恢复原状态" : "收藏失败，请稍后重试",
      );
      return wasFavorited;
    } finally {
      pending.delete(universityId);
    }
  }
  async function remove(universityId: number, universityName?: string) {
    if (!has(universityId)) return false;
    return toggle(universityId, universityName);
  }

  // 切换账号时清空本地收藏状态并重新拉取
  watch(
    () => auth.user?.id,
    () => {
      ids.value = [];
      loaded.value = false;
      void load();
    },
  );

  return { ids, loaded, loading, has, load, toggle, remove, sync };
});
