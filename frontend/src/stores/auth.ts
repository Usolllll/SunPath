import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "../api";
import type { User } from "../api/types";

export const useAuth = defineStore("auth", () => {
  const token = ref(localStorage.getItem("sunpath.token") || "");
  const user = ref<User | null>(null);
  const hydrated = ref(false);
  function accept(data: { access_token: string; user: User }) {
    token.value = data.access_token;
    user.value = data.user;
    hydrated.value = true;
    localStorage.setItem("sunpath.token", data.access_token);
  }
  function clear() {
    token.value = "";
    user.value = null;
    hydrated.value = false;
    localStorage.removeItem("sunpath.token");
  }
  async function load() {
    if (token.value && !hydrated.value) {
      try {
        user.value = (await api.me()).data;
        hydrated.value = true;
      } catch {
        clear();
      }
    }
  }
  return { token, user, hydrated, accept, clear, load };
});
