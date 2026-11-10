import type { PriorityMode, Weights } from "../api/types";

/** 三档决策模式：只改变同一梯度内的选择与顺序，不改变候选池与冲稳保配额 */
export const MODE_LABELS: Record<PriorityMode, string> = {
  school: "偏学校",
  balanced: "均衡",
  major: "偏专业",
};
export const MODE_HINTS: Record<PriorityMode, string> = {
  school: "优先院校层次与城市",
  balanced: "院校与专业并重",
  major: "优先专业对口",
};
/** 后端 /meta 未返回时使用的兜底权重（与 backend/app/services/scoring.py 一致） */
export const MODE_WEIGHTS: Record<PriorityMode, Weights> = {
  school: { school: 0.6, major: 0.15, fit: 0.25 },
  balanced: { school: 0.4, major: 0.4, fit: 0.2 },
  major: { school: 0.15, major: 0.6, fit: 0.25 },
};
export const MODES: PriorityMode[] = ["school", "balanced", "major"];

export const percent = (value: number) => `${Math.round(value * 100)}%`;

/** “当前权重：院校 60% · 专业 15% · 位次适配 25%” */
export function weightLine(weights?: Weights | null): string {
  if (!weights) return "权重加载中…";
  return `院校 ${percent(weights.school)} · 专业 ${percent(weights.major)} · 位次适配 ${percent(weights.fit)}`;
}

/** 金额（元）→ “10.1 万”；缺数据统一写“未收录” */
export function wan(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "未收录";
  const w = value / 10000;
  return `${w.toFixed(1).replace(/\.0$/, "")} 万`;
}
export const yuan = (value: number | null | undefined) =>
  value == null || Number.isNaN(value)
    ? "未收录"
    : `¥ ${value.toLocaleString("zh-CN")}`;

/** 超出家庭预算的差额文案；未超预算/未设预算返回 null */
export function overBudgetText(
  total: number | null | undefined,
  budget: number | null | undefined,
): string | null {
  if (total == null || budget == null || budget <= 0 || total <= budget)
    return null;
  return `超预算 ${wan(total - budget)}`;
}

/** 家庭四年预算分档（与 backend/app/services/budget.py 的 BUDGET_TIERS 一致） */
export function budgetTier(total: number | null | undefined): string {
  if (total == null) return "未设置";
  if (total <= 80000) return "经济型";
  if (total <= 120000) return "常规型";
  if (total <= 200000) return "宽裕型";
  if (total <= 350000) return "高投入型";
  return "自定";
}

export const CITY_TIER_LABELS: Record<number, string> = {
  1: "一线城市",
  2: "新一线城市",
  3: "二线城市",
  4: "三线城市",
};
export function cityTierLabel(tier?: number | null): string {
  if (tier == null) return "城市分级未收录";
  return CITY_TIER_LABELS[tier] ?? `城市 ${tier} 档`;
}
/** 院校层次分（100/85/70/50/30，由 985/211/双一流名单换算，仅用于内部排序） */
export function levelTierLabel(tier?: number | null): string {
  return tier == null ? "层次未收录" : `层次分 ${tier}`;
}

export const TRANSFER_LABELS: Record<number, string> = {
  1: "转专业较难",
  2: "转专业一般",
  3: "转专业友好",
};
/** 转专业友好度 1–3 星；未收录返回 null，界面显示“未收录” */
export function transferStars(
  friendly?: number | null,
): { stars: string; label: string; score: number } | null {
  if (friendly == null || !Number.isFinite(friendly)) return null;
  const score = Math.max(1, Math.min(3, Math.round(friendly)));
  return {
    stars: "★".repeat(score) + "☆".repeat(3 - score),
    label: TRANSFER_LABELS[score] ?? "转专业未收录",
    score,
  };
}

export const RIASEC_LABELS: Record<string, string> = {
  R: "现实型",
  I: "研究型",
  A: "艺术型",
  S: "社会型",
  E: "企业型",
  C: "常规型",
};
export const riasecLabel = (key: string) =>
  RIASEC_LABELS[key] ? `${key} · ${RIASEC_LABELS[key]}` : key;
