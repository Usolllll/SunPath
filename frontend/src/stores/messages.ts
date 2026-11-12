import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { api } from "../api";
import { useAuth } from "./auth";

/**
 * 消息未读数（顶部铃铛 + 侧栏角标共用）。
 * 只缓存未读数；完整消息列表由 /messages 页面自己拉取。
 * 未读数接口失败时静默处理，不阻塞页面。
 */
export const useMessages = defineStore("messages", () => {
  const auth = useAuth();
  const unread = ref(0);
  const loaded = ref(false);
  const loading = ref(false);
  let inflight: Promise<void> | null = null;

  async function load(force = false): Promise<void> {
    if (!auth.token) {
      unread.value = 0;
      loaded.value = false;
      return;
    }
    if (inflight) return inflight;
    if (loaded.value && !force) return;
    loading.value = true;
    inflight = (async () => {
      try {
        unread.value = (await api.unreadCount()).data.unread ?? 0;
        loaded.value = true;
      } catch {
        /* 未读数获取失败时保持现状，不打扰用户 */
      } finally {
        loading.value = false;
        inflight = null;
      }
    })();
    return inflight;
  }
  function setUnread(value: number) {
    unread.value = Math.max(0, Math.floor(Number(value) || 0));
    loaded.value = true;
  }
  function markRead(count = 1) {
    unread.value = Math.max(0, unread.value - Math.max(0, count));
  }
  function clearUnread() {
    unread.value = 0;
    loaded.value = true;
  }

  watch(
    () => auth.user?.id,
    () => {
      unread.value = 0;
      loaded.value = false;
      void load();
    },
  );

  return { unread, loaded, loading, load, setUnread, markRead, clearUnread };
});
