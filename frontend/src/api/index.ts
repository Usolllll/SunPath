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
  RealDataSummary,
  RealDataRows,
  RealDataSchool,
  PlanBatch,
  Favorite,
  FavoriteIds,
  FaqResult,
  DataDictionary,
  DataQuality,
  PopularityResult,
  ProfileCompleteness,
  ProcessSchedule,
  ProcessResults,
  ProcessCollection,
  NoticeItem,
  NoticeResult,
  MessagesResult,
  MessageUnread,
  MessageRefreshResult,
  MessageSubscription,
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
  /** 官方真实投档数据：覆盖省份、行数、公告发布时间与来源（需登录） */
  realDataSummary: () => http.get<RealDataSummary>("/real-data/summary"),
  /**
   * 官方真实投档明细（服务端分页，单省 14 万条量级，勿全量拉取）。
   * province 仅支持 辽宁 / 贵州 / 黑龙江；其他省份后端返回 422（该省官方数据尚未收录）。
   */
  realDataRows: (params: {
    province: string;
    year?: number | null;
    q?: string;
    page?: number;
    page_size?: number;
  }) => http.get<RealDataRows>("/real-data/rows", { params }),
  /** 单校官方投档核对（最近一年 + 近 20 条记录） */
  realDataSchool: (name: string, province: string) =>
    http.get<RealDataSchool>("/real-data/school", {
      params: { name, province },
    }),
  overview: () =>
    http.get<{
      universities: number;
      groups: number;
      plans: number;
      data_label: string;
    }>("/overview"),
  plans: () => http.get<Plan[]>("/plans"),
  /** 保存 / 更新方案；RTM 新增 batch（'本科批'|'专科批'），仅草稿可编辑 */
  savePlan: (
    name: string,
    group_ids: number[],
    id?: number,
    batch: PlanBatch = "本科批",
  ) =>
    id
      ? http.put<Plan>(`/plans/${id}`, { name, group_ids, batch })
      : http.post<Plan>("/plans", { name, group_ids, batch }),
  deletePlan: (id: number) => http.delete(`/plans/${id}`),
  exportPlan: (id: number) =>
    http.get<Blob>(`/plans/${id}/export`, { responseType: "blob" }),
  /**
   * 提交方案（RTM）。Idempotency-Key 由前端生成：同一草稿重试复用同一个 key，
   * 提交成功后清空；后端按 key 幂等，避免重复提交产生多份记录。
   */
  submitPlan: (id: number, idempotencyKey: string) =>
    http.post<Plan>(`/plans/${id}/submit`, null, {
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  /** 撤回到草稿（RTM）：仅已提交方案可撤回 */
  withdrawPlan: (id: number) => http.post<Plan>(`/plans/${id}/withdraw`),
  // ---------------------------------------------------------------- RTM：收藏
  favorites: () => http.get<Favorite[]>("/favorites"),
  favoriteIds: () => http.get<FavoriteIds>("/favorites/ids"),
  addFavorite: (university_id: number) =>
    http.post<Favorite>("/favorites", { university_id }),
  removeFavorite: (university_id: number) =>
    http.delete(`/favorites/${university_id}`),
  // ---------------------------------------------------------------- RTM：运营 / 数据质量
  faq: (params: { q?: string; category?: string } = {}) =>
    http.get<FaqResult>("/ops/faq", { params }),
  dictionary: () => http.get<DataDictionary>("/ops/dictionary"),
  dataQuality: () => http.get<DataQuality>("/ops/data-quality"),
  popularity: (limit = 10) =>
    http.get<PopularityResult>("/ops/popularity", { params: { limit } }),
  profileCompleteness: () =>
    http.get<ProfileCompleteness>("/ops/profile-completeness"),
  // ---------------------------------------------------------------- M7：录取进程 / 模拟投档 / 征集
  /** 分批次录取进程时间轴（done/active/upcoming） */
  processSchedule: (province: string) =>
    http.get<ProcessSchedule>("/process/schedule", { params: { province } }),
  /** 按方案逐条比对官方投档最低位次，生成模拟投档判定（不代表录取结果） */
  processResults: (planId: number) =>
    http.get<ProcessResults>(`/process/results/${planId}`),
  processResultsExport: (planId: number) =>
    http.get<Blob>(`/process/results/${planId}/export`, {
      responseType: "blob",
    }),
  /** 征集志愿时间窗口与剩余天数 */
  processCollection: (province: string) =>
    http.get<ProcessCollection>("/process/collection", {
      params: { province },
    }),
  // ---------------------------------------------------------------- M8：政策资讯 / 消息 / 订阅
  notices: (params: { category?: string; q?: string; limit?: number } = {}) =>
    http.get<NoticeResult>("/notices", { params }),
  notice: (id: number | string) => http.get<NoticeItem>(`/notices/${id}`),
  messages: (onlyUnread = false) =>
    http.get<MessagesResult>("/messages", {
      params: { only_unread: onlyUnread },
    }),
  unreadCount: () => http.get<MessageUnread>("/messages/unread-count"),
  readMessage: (id: number) => http.post(`/messages/${id}/read`),
  readAllMessages: () => http.post("/messages/read-all"),
  /** 触发后端重新检查并生成提醒；返回新增条数等字段 */
  refreshMessages: () => http.post<MessageRefreshResult>("/messages/refresh"),
  messageSubscription: () =>
    http.get<MessageSubscription>("/messages/subscription"),
  saveMessageSubscription: (data: MessageSubscription) =>
    http.put<MessageSubscription>("/messages/subscription", data),
};
