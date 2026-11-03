import { http } from "./http";
import type {
  User,
  Profile,
  Plan,
  Recommendation,
  Catalog,
  Group,
  ChatMessage,
  ChatReply,
  ChatAvailableContext,
} from "./types";
export const api = {
  chatConfig: () =>
    http.get<{ configured: boolean; model_label: string }>("/chat/config"),
  chatContext: () => http.get<ChatAvailableContext>("/chat/context"),
  chat: (
    messages: ChatMessage[],
    options: {
      use_profile: boolean;
      use_saved_plans: boolean;
      plan_ids: number[] | null;
    },
    signal: AbortSignal,
  ) =>
    http.post<ChatReply>(
      "/chat",
      { messages, ...options },
      { timeout: 135000, signal },
    ),
  login: (data: { email: string; password: string }) =>
    http.post<{ access_token: string; user: User }>("/auth/login", data),
  register: (data: { email: string; password: string; name: string }) =>
    http.post<{ access_token: string; user: User }>("/auth/register", data),
  me: () => http.get<User>("/auth/me"),
  logout: () => http.post("/auth/logout"),
  profile: (data: Profile) => http.put<User>("/auth/profile", data),
  name: (name: string) => http.patch<User>("/auth/me", { name }),
  password: (data: { current_password: string; new_password: string }) =>
    http.put("/auth/password", data),
  recommendations: () => http.get<Recommendation>("/recommendations"),
  aiMatch: (count: number, signal: AbortSignal) =>
    http.post<Recommendation>(
      "/recommendations/ai",
      { count },
      { timeout: 135000, signal },
    ),
  meta: () => http.get<{ regions: string[] }>("/meta"),
  generate: (count = 12) =>
    http.post<{ items: Group[]; missing_tiers: string[]; message: string }>(
      "/recommendations/generate",
      null,
      { params: { count } },
    ),
  catalog: (params: Record<string, unknown>) =>
    http.get<Catalog>("/catalog", { params }),
  overview: () =>
    http.get<{
      universities: number;
      groups: number;
      plans: number;
      data_label: string;
    }>("/overview"),
  plans: () => http.get<Plan[]>("/plans"),
  savePlan: (name: string, group_ids: number[], id?: number) =>
    id
      ? http.put<Plan>(`/plans/${id}`, { name, group_ids })
      : http.post<Plan>("/plans", { name, group_ids }),
  deletePlan: (id: number) => http.delete(`/plans/${id}`),
  exportPlan: (id: number) =>
    http.get<Blob>(`/plans/${id}/export`, { responseType: "blob" }),
};
