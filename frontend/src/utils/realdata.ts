/**
 * 官方真实投档数据的展示辅助函数。
 * 这里只做格式化与安全过滤，不引入任何第三方依赖，方便组件与 node 测试共用。
 * 真实数据的所有条目都来自省考试院公开文件，界面必须可追溯到来源并保留声明。
 */

/** 后端 real-data 接口当前支持的生源省份（其他省份返回 422） */
export const REAL_DATA_PROVINCES = ["辽宁", "贵州", "黑龙江"] as const;

export interface ProvinceLike {
  province: string;
  rows: number;
  schools?: number;
  years?: number[];
}

export interface SummaryLike {
  total_rows: number;
  provinces: ProvinceLike[];
}

export interface OfficialLike {
  exam_year?: number | null;
  min_rank?: number | null;
  subject_type?: string | null;
}

function count(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "0";
  return Number(value).toLocaleString("zh-CN");
}

/** 年份区间：连续或不连续都只显示首尾，例 "2023–2026"；单一年份显示 "2026" */
export function yearSpan(years: number[] | null | undefined): string {
  const list = (years ?? [])
    .filter((year) => Number.isFinite(year))
    .slice()
    .sort((a, b) => a - b);
  if (!list.length) return "年份未标注";
  const first = list[0];
  const last = list[list.length - 1];
  return first === last ? String(first) : `${first}–${last}`;
}

/** 数据新鲜度条文案：覆盖 3 省 / 142,531 条 / 辽宁 2023–2026 · 贵州 2024–2026 */
export function coverageText(summary: SummaryLike | null | undefined): string {
  const provinces = summary?.provinces ?? [];
  if (!provinces.length) return "官方投档数据尚未收录";
  const order = (name: string) => {
    const index = REAL_DATA_PROVINCES.indexOf(
      name as (typeof REAL_DATA_PROVINCES)[number],
    );
    return index < 0 ? 99 : index;
  };
  const ordered = provinces.slice().sort((a, b) => order(a.province) - order(b.province));
  const parts = ordered.map((item) => `${item.province} ${yearSpan(item.years)}`);
  return `覆盖 ${ordered.length} 省 / ${count(summary?.total_rows)} 条 / ${parts.join(" · ")}`;
}

/**
 * 推荐卡片 / 抽屉里的官方核对文案：
 * "官方 2026 投档最低位次 1,235（历史类）"；缺位次时降级，未收录返回 null。
 */
export function officialCheckText(
  official: OfficialLike | null | undefined,
): string | null {
  if (!official || !official.exam_year) return null;
  const year = official.exam_year;
  if (official.min_rank == null || !Number.isFinite(official.min_rank)) {
    return `官方 ${year} 年投档记录（最低位次未收录）`;
  }
  const rank = Number(official.min_rank).toLocaleString("zh-CN");
  const subject = official.subject_type ? `（${official.subject_type}）` : "";
  return `官方 ${year} 投档最低位次 ${rank}${subject}`;
}

/** 只允许 http(s) 来源链接进入 href，避免 javascript:/data: 之类的来源字段 */
export function safeSourceUrl(url: string | null | undefined): string | null {
  const value = (url ?? "").trim();
  return /^https?:\/\//i.test(value) ? value : null;
}
