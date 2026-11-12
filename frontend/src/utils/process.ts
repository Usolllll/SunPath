/**
 * M7/M8 展示辅助的纯函数：录取进程状态、模拟投档判定、征集倒计时、导出文件名、
 * 消息刷新条数与类型文案。不依赖 Vue / 浏览器，便于 node 测试复用。
 * 注意：模拟投档判定只按官方投档最低位次做演示，不代表录取结果或概率。
 */

export const NOTICE_CATEGORY_FALLBACK = [
  "招生政策",
  "志愿填报",
  "数据公告",
  "院校宣讲",
] as const;

export interface MessageTypeOption {
  value: string;
  label: string;
}

/** 订阅/消息类型选项：与后端 SUBSCRIPTION_TYPES 保持一致（collection/plan/policy/lecture/quality） */
export const MESSAGE_TYPE_OPTIONS: MessageTypeOption[] = [
  { value: "collection", label: "征集提醒" },
  { value: "plan", label: "方案提醒" },
  { value: "policy", label: "政策公告" },
  { value: "lecture", label: "院校宣讲" },
  { value: "quality", label: "数据质量" },
  { value: "result", label: "结果推送" },
];

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  collection: "征集提醒",
  plan: "方案提醒",
  policy: "政策公告",
  lecture: "院校宣讲",
  quality: "数据质量",
  result: "结果推送",
  // 兼容历史消息里出现过的旧取值
  notice: "政策公告",
  data_quality: "数据质量",
};

export function messageTypeLabel(type: string | null | undefined): string {
  const key = (type ?? "").trim();
  if (!key) return "系统消息";
  return MESSAGE_TYPE_LABELS[key] ?? key;
}

/** 录取进程节点状态：done 已完成 / active 进行中 / upcoming 未开始 */
export function processStateLabel(state: string | null | undefined): string {
  if (state === "done") return "已完成";
  if (state === "active") return "进行中";
  if (state === "upcoming") return "未开始";
  return "待公布";
}

export function processStateClass(state: string | null | undefined): string {
  if (state === "done" || state === "active" || state === "upcoming")
    return state;
  return "upcoming";
}

/**
 * 单个时间节点的展示状态：
 * event.state 是后端按“今天”实时计算出的权威状态（services/process._state），优先使用；
 * event.status 只是数据文件里的旧样例、可能过时（后端已置为 null），仅在 state 缺失时兜底。
 */
export function resolveEventState(event: {
  state?: string | null;
  status?: string | null;
} | null | undefined): string {
  const state = (event?.state ?? "").trim();
  if (state === "done" || state === "active" || state === "upcoming")
    return state;
  const status = (event?.status ?? "").trim();
  if (status === "done" || status === "active" || status === "upcoming")
    return status;
  return "";
}

/** 模拟投档判定：pass 达到 / fail 未达到 / no_data 暂无官方投档数据 */
export function verdictLabel(verdict: string | null | undefined): string {
  if (verdict === "pass") return "达到近一次官方投档最低位次";
  if (verdict === "fail") return "未达到近一次官方投档最低位次";
  if (verdict === "no_data") return "暂无官方投档数据";
  return "待核对";
}

export function verdictClass(verdict: string | null | undefined): string {
  if (verdict === "pass") return "pass";
  if (verdict === "fail") return "fail";
  return "no-data";
}

export interface VerdictSummaryLike {
  total: number;
  pass: number;
  fail: number;
  no_data: number;
}

/** 结果汇总文案：共 12 条 · 达到 3 · 未达到 5 · 暂无官方数据 4 */
export function summaryText(
  summary: VerdictSummaryLike | null | undefined,
): string {
  if (!summary) return "暂无投档结果";
  const total = Number.isFinite(summary.total) ? summary.total : 0;
  return `共 ${total} 条 · 达到 ${summary.pass ?? 0} · 未达到 ${summary.fail ?? 0} · 暂无官方数据 ${summary.no_data ?? 0}`;
}

/** 征集志愿状态文案：done/ended → 已结束，upcoming → 即将开始 */
export function collectionStatusLabel(
  status: string | null | undefined,
): string {
  const value = (status ?? "").trim();
  if (!value) return "";
  const key = value.toLowerCase();
  if (["done", "ended", "finished", "closed", "已结束"].includes(key))
    return "已结束";
  if (["active", "进行中", "running"].includes(key)) return "进行中";
  if (["upcoming", "pending", "未开始", "即将开始"].includes(key))
    return "即将开始";
  return value;
}

/**
 * 征集志愿倒计时：时间未公布 / 已结束 / 今天截止 / 还剩 N 天。
 * 后端对已结束窗口可能仍给 days_left=0，需优先看 status，避免误显示“今天截止”。
 */
export function collectionCountdown(collection: {
  days_left?: number | null;
  status?: string | null;
} | null | undefined): string {
  if (!collection) return "时间待公布";
  const statusLabel = collectionStatusLabel(collection.status);
  if (statusLabel === "已结束") return "已结束";
  const days = collection.days_left;
  if (days == null || !Number.isFinite(days)) {
    return statusLabel || "时间待公布";
  }
  if (days < 0) return "已结束";
  if (days === 0) return "今天截止";
  return `还剩 ${days} 天`;
}

/** 倒计时紧迫度：ended / urgent（≤3 天）/ active / pending */
export function collectionTone(
  daysLeft: number | null | undefined,
  status?: string | null,
): "ended" | "urgent" | "active" | "pending" {
  if (collectionStatusLabel(status) === "已结束") return "ended";
  if (daysLeft == null || !Number.isFinite(daysLeft)) return "pending";
  if (daysLeft < 0) return "ended";
  if (daysLeft <= 3) return "urgent";
  return "active";
}

/** 时间窗口：start ~ end / start 起 / 至 end / 同一天只显示一次 / 时间待公布 */
export function windowText(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  const from = (start ?? "").trim();
  const to = (end ?? "").trim();
  if (from && to) return from === to ? from : `${from} ~ ${to}`;
  if (from) return `${from} 起`;
  if (to) return `至 ${to}`;
  return "时间待公布";
}

/**
 * 时间轴更新时间的展示：真实数据可能只给到年月（如 "2026-11"），
 * 不能直接 new Date() 否则会变成 Invalid Date。
 */
export function updatedAtText(value: string | null | undefined): string {
  const text = (value ?? "").trim();
  if (!text) return "更新时间未标注";
  const month = /^(\d{4})-(\d{2})$/.exec(text);
  if (month) return `${month[1]} 年 ${month[2]} 月`;
  return text;
}

/**
 * 有些后端把中文文件名直接塞进 Content-Disposition 的 filename，
 * 浏览器/axios 按 latin1 读出来会变成“æ¨¡æ‹Ÿ”这类乱码。
 * 这里在“整串按 UTF-8 可解码”时还原；真正的 latin1 文件名（如 café.csv）会解码失败并保持原样。
 */
function decodeLatin1Mojibake(value: string): string {
  if (!/[\u0080-\u00ff]/.test(value)) return value;
  try {
    const bytes = Uint8Array.from(value, (char) => char.charCodeAt(0) & 0xff);
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return value;
  }
}

/**
 * 从 Content-Disposition 解析下载文件名：
 * 支持 filename="x.csv"、filename=x.csv、filename*=UTF-8''%E6%A8%A1.csv。
 * 只取 basename，避免路径注入；解析不出返回 null，由调用方给默认名。
 */
export function filenameFromDisposition(
  header: string | null | undefined,
): string | null {
  const value = (header ?? "").trim();
  if (!value) return null;
  const utf8 = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(value);
  let name: string | null = null;
  if (utf8) {
    try {
      name = decodeURIComponent(utf8[1]);
    } catch {
      name = utf8[1];
    }
  } else {
    const plain = /filename\s*=\s*("([^"]*)"|([^;]+))/.exec(value);
    if (plain) name = (plain[2] ?? plain[3] ?? "").trim();
  }
  if (!name) return null;
  const base = decodeLatin1Mojibake(name).split(/[\\/]/).pop() ?? "";
  return base.trim() || null;
}

/**
 * POST /messages/refresh 的返回字段在不同实现里可能是 created/added/new/new_count，
 * 统一取第一个有效数字；没有则返回 0。
 */
export function newMessagesCount(
  payload: Record<string, unknown> | null | undefined,
): number {
  if (!payload) return 0;
  for (const key of ["created", "added", "new", "new_count"]) {
    const value = payload[key];
    if (typeof value === "number" && Number.isFinite(value) && value > 0)
      return Math.floor(value);
  }
  return 0;
}
