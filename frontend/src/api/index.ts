import { http } from "./http";
import type {
  User,
  Profile,
  Plan,
  Recommendation,
  Catalog,
  Group,
} from "./types";
export const api = {
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
  generate: () =>
    http.post<{ items: Group[]; missing_tiers: string[]; message: string }>(
      "/recommendations/generate",
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
