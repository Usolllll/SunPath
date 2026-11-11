/**
 * RTM 前端纯函数：方案批次/状态、可编辑性、提交幂等 key、收藏 id 列表切换。
 * 不依赖 Vue / 浏览器（crypto 由调用方注入），便于 node 测试复用。
 */

export const PLAN_BATCHES = ["本科批", "专科批"] as const;
export type PlanBatchValue = (typeof PLAN_BATCHES)[number];
export type PlanStatusValue = "draft" | "submitted";

/** 已提交方案被编辑/删除时给用户的统一提示（服务端 409 也用它） */
export const SUBMIT_LOCK_MESSAGE = "已提交的方案不可编辑，请先撤回";

export interface SubmitKeyState {
  signature: string;
  key: string;
}

function isBatch(value: unknown): value is PlanBatchValue {
  return value === "本科批" || value === "专科批";
}

/** 批次展示：缺失或非法值一律按「本科批」，不臆造其他批次 */
export function planBatchLabel(batch: unknown): PlanBatchValue {
  return isBatch(batch) ? batch : "本科批";
}

/** 状态展示：除明确的 submitted 外都按草稿处理（旧版本后端无 status 字段） */
export function planStatusLabel(status: unknown): "草稿" | "已提交" {
  return status === "submitted" ? "已提交" : "草稿";
}

/** 只有草稿可编辑；已提交必须先撤回 */
export function isPlanEditable(status: unknown): boolean {
  return status !== "submitted";
}

/** 收藏 id 列表的不可变切换（乐观更新用）：已存在则移除，否则追加 */
export function toggleId(ids: readonly number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
}

export function hasId(ids: readonly number[], id: number): boolean {
  return ids.includes(id);
}

/**
 * 提交幂等 key 的草稿签名：同一方案 id + 名称 + 批次 + 专业组顺序 → 同一个签名。
 * 签名不变时重试提交复用同一 Idempotency-Key；草稿一变，签名变化，下次提交换新 key。
 */
export function idempotencySignature(input: {
  planId: number | null | undefined;
  name: string;
  batch: unknown;
  itemIds: readonly number[];
}): string {
  return [
    input.planId ?? "draft",
    (input.name || "").trim(),
    planBatchLabel(input.batch),
    input.itemIds.join(","),
  ].join("|");
}

/**
 * 计算本次提交使用的 key：
 * - 同签名且已有 key → 复用（提交失败重试不会产生第二份记录）
 * - 签名变化 / 首次提交 → 调用 generate() 生成新 key
 */
export function submitKeyFor(
  signature: string,
  state: SubmitKeyState,
  generate: () => string,
): SubmitKeyState {
  if (state.signature === signature && state.key) return state;
  return { signature, key: generate() };
}

/** 提交成功后清空 key 状态；该草稿下次提交重新生成 */
export function clearedSubmitKey(): SubmitKeyState {
  return { signature: "", key: "" };
}

/** 校验 Idempotency-Key 是否为 1–64 个可见 ASCII 字符（与后端约束对齐） */
export function isValidSubmitKey(value: string): boolean {
  return /^[\x21-\x7e]{1,64}$/.test(value);
}

/**
 * 巡检时间可能是紧凑格式 20261110_153319，也可能是 ISO；统一转成可读文本。
 * 无法识别时原样显示，不猜测日期。
 */
export function patrolCheckedText(value: unknown): string {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) return "未标注";
  const compact = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/.exec(text);
  if (compact)
    return `${compact[1]}-${compact[2]}-${compact[3]} ${compact[4]}:${compact[5]}`;
  return text;
}
