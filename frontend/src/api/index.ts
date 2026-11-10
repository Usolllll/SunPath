import { http } from "./http";
import type {
  User,
  Profile,
  Plan,
  Recommendation,
  RecommendationCompare,
  GeneratedPlan,
  PriorityMode,
  Catalog,
  Group,
  MajorList,
  MajorCard,
  Coverage,
  Readiness,
  BudgetEstimate,
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
  /** v2：mode = 取舍沙盘的排序模式；budget_cap 为显式预算硬筛（默认不隐藏候选） */
  recommendations: (options: { mode?: PriorityMode; budget_cap?: number } = {}) =>
    http.get<Recommendation>("/recommendations", {
      params: {
        ...(options.mode ? { mode: options.mode } : {}),
        ...(options.budget_cap ? { budget_cap: options.budget_cap } : {}),
      },
    }),
  /** v2：同一候选池、同一配额下两种模式的并排差异 */
  compare: (
    mode_a: PriorityMode,
    mode_b: PriorityMode,
    count = 12,
  ) =>
    http.get<RecommendationCompare>("/recommendations/compare", {
      params: { mode_a, mode_b, count },
    }),
  /** v2：按当前模式生成冲稳保方案（1:2:1 配额） */
  generatePlan: (count = 12, mode?: PriorityMode) =>
    http.post<GeneratedPlan>("/recommendations/generate", null, {
      params: { count, ...(mode ? { mode } : {}) },
    }),
  aiMatch: (count: number, signal: AbortSignal) =>
    http.post<Recommendation>(
      "/recommendations/ai",
      { count },
      { timeout: 135000, signal },
    ),
  majors: () => http.get<MajorList>("/majors"),
  majorDetail: (name: string) =>
    http.get<MajorCard>(`/majors/${encodeURIComponent(name)}`),
  coverage: () => http.get<Coverage>("/options/coverage"),
  readiness: (groupId: number) => http.get<Readiness>(`/groups/${groupId}/readiness`),
  budgetEstimate: (groupId: number) =>
    http.get<BudgetEstimate>("/budget/estimate", { params: { group_id: groupId } }),
  meta: () =>
    http.get<{
      regions: string[];
      modes: { key: PriorityMode; label: string; weights: Record<string, number> }[];
      budget_tiers: { name: string; range: string }[];
      engine_version: string;
      disclaimer: string;
    }>("/meta"),
  catalog: (params: Record<string, unknown>) =>
    http.get<Catalog>("/catalog", { params }),
  catalogDetail: (id: number, params: Record<string, unknown>) =>
    http.get<Group>(`/catalog/${id}`, { params }),
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
