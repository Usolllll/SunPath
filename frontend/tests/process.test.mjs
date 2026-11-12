import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(
  new URL("../src/utils/process.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
}).outputText;
const exports = {};
new Function("require", "exports", compiled)(
  createRequire(import.meta.url),
  exports,
);
const {
  NOTICE_CATEGORY_FALLBACK,
  MESSAGE_TYPE_OPTIONS,
  collectionCountdown,
  collectionStatusLabel,
  collectionTone,
  filenameFromDisposition,
  messageTypeLabel,
  newMessagesCount,
  processStateClass,
  processStateLabel,
  resolveEventState,
  summaryText,
  updatedAtText,
  verdictClass,
  verdictLabel,
  windowText,
} = exports;

test("process timeline states map to three visual states", () => {
  assert.equal(processStateLabel("done"), "已完成");
  assert.equal(processStateLabel("active"), "进行中");
  assert.equal(processStateLabel("upcoming"), "未开始");
  assert.equal(processStateLabel(null), "待公布");
  assert.equal(processStateClass("done"), "done");
  assert.equal(processStateClass("active"), "active");
  assert.equal(processStateClass("weird"), "upcoming");
});

test("event node state trusts backend real-time state over stale status", () => {
  // state 是后端按“今天”实时算的权威状态；status 是数据文件旧样例（可能过时）
  assert.equal(resolveEventState({ state: "done", status: "upcoming" }), "done");
  assert.equal(resolveEventState({ state: "upcoming", status: "done" }), "upcoming");
  assert.equal(resolveEventState({ state: "active", status: null }), "active");
  // state 缺失时用 status 兜底
  assert.equal(resolveEventState({ state: null, status: "upcoming" }), "upcoming");
  assert.equal(resolveEventState({ state: "", status: "" }), "");
  assert.equal(resolveEventState(null), "");
});

test("simulated admission verdicts never claim a real admission result", () => {
  assert.equal(verdictLabel("pass"), "达到近一次官方投档最低位次");
  assert.equal(verdictLabel("fail"), "未达到近一次官方投档最低位次");
  assert.equal(verdictLabel("no_data"), "暂无官方投档数据");
  assert.equal(verdictLabel("unknown"), "待核对");
  assert.equal(verdictClass("pass"), "pass");
  assert.equal(verdictClass("fail"), "fail");
  assert.equal(verdictClass(undefined), "no-data");
  for (const label of ["pass", "fail", "no_data"].map(verdictLabel))
    assert.ok(!/录取概率|包过/.test(label));
});

test("result summary counts total / pass / fail / no_data", () => {
  assert.equal(
    summaryText({ total: 12, pass: 3, fail: 5, no_data: 4 }),
    "共 12 条 · 达到 3 · 未达到 5 · 暂无官方数据 4",
  );
  assert.equal(
    summaryText({ total: 0, pass: 0, fail: 0, no_data: 0 }),
    "共 0 条 · 达到 0 · 未达到 0 · 暂无官方数据 0",
  );
  assert.equal(summaryText(null), "暂无投档结果");
});

test("collection countdown handles pending, ended, today and remaining days", () => {
  assert.equal(collectionCountdown(null), "时间待公布");
  assert.equal(collectionCountdown({ days_left: null, status: "未开始" }), "即将开始");
  assert.equal(collectionCountdown({ days_left: -1 }), "已结束");
  assert.equal(collectionCountdown({ days_left: 0 }), "今天截止");
  // 真实数据：窗口已结束但 days_left 仍为 0，优先按 status 显示已结束
  assert.equal(
    collectionCountdown({ days_left: 0, status: "done" }),
    "已结束",
  );
  assert.equal(collectionCountdown({ days_left: 6 }), "还剩 6 天");
  assert.equal(collectionStatusLabel("done"), "已结束");
  assert.equal(collectionStatusLabel("upcoming"), "即将开始");
  assert.equal(collectionStatusLabel("active"), "进行中");
  assert.equal(collectionStatusLabel("自定义"), "自定义");
  assert.equal(collectionTone(null), "pending");
  assert.equal(collectionTone(-2), "ended");
  assert.equal(collectionTone(0, "done"), "ended");
  assert.equal(collectionTone(2), "urgent");
  assert.equal(collectionTone(9), "active");
});

test("window text degrades without inventing dates", () => {
  assert.equal(windowText("2026-07-01", "2026-07-05"), "2026-07-01 ~ 2026-07-05");
  // 单日节点不重复显示同一日期
  assert.equal(windowText("2026-06-25", "2026-06-25"), "2026-06-25");
  assert.equal(windowText("2026-07-01", null), "2026-07-01 起");
  assert.equal(windowText(null, "2026-07-05"), "至 2026-07-05");
  assert.equal(windowText(null, null), "时间待公布");
});

test("updated_at only shows month for year-month data", () => {
  assert.equal(updatedAtText("2026-11"), "2026 年 11 月");
  assert.equal(updatedAtText("2026-11-11"), "2026-11-11");
  assert.equal(updatedAtText(""), "更新时间未标注");
  assert.equal(updatedAtText(null), "更新时间未标注");
});

test("download filename is parsed safely from Content-Disposition", () => {
  assert.equal(
    filenameFromDisposition('attachment; filename="SunPath-投档结果.csv"'),
    "SunPath-投档结果.csv",
  );
  assert.equal(
    filenameFromDisposition("attachment; filename=result.csv"),
    "result.csv",
  );
  assert.equal(
    filenameFromDisposition(
      "attachment; filename*=UTF-8''%E6%A8%A1%E6%8B%9F%E6%8A%95%E6%A1%A3.csv",
    ),
    "模拟投档.csv",
  );
  assert.equal(
    filenameFromDisposition('attachment; filename="../../etc/passwd"'),
    "passwd",
  );
  // 后端把中文直接放进 filename 时，浏览器按 latin1 读出会乱码；应还原为中文
  const mojibake = Buffer.from("模拟投档结果.csv", "utf8").toString("latin1");
  assert.equal(
    filenameFromDisposition(`attachment; filename="${mojibake}"`),
    "模拟投档结果.csv",
  );
  // 真正的 latin1 文件名（é 不是合法 UTF-8 序列）保持原样
  assert.equal(
    filenameFromDisposition('attachment; filename="café.csv"'),
    "café.csv",
  );
  assert.equal(filenameFromDisposition(null), null);
  assert.equal(filenameFromDisposition("attachment"), null);
});

test("message refresh count tolerates different backend field names", () => {
  assert.equal(newMessagesCount({ created: 3 }), 3);
  assert.equal(newMessagesCount({ added: 2 }), 2);
  assert.equal(newMessagesCount({ new: 1 }), 1);
  assert.equal(newMessagesCount({ new_count: 5 }), 5);
  assert.equal(newMessagesCount({ created: 0, added: 4 }), 4);
  assert.equal(newMessagesCount({ unread: 9 }), 0);
  assert.equal(newMessagesCount(null), 0);
});

test("message and notice dictionaries match the product copy", () => {
  assert.deepEqual(
    MESSAGE_TYPE_OPTIONS.map((item) => item.label),
    ["征集提醒", "方案提醒", "政策公告", "院校宣讲", "数据质量"],
  );
  assert.deepEqual(
    MESSAGE_TYPE_OPTIONS.map((item) => item.value),
    ["collection", "plan", "policy", "lecture", "quality"],
  );
  assert.equal(messageTypeLabel("collection"), "征集提醒");
  assert.equal(messageTypeLabel("plan"), "方案提醒");
  assert.equal(messageTypeLabel("policy"), "政策公告");
  assert.equal(messageTypeLabel("lecture"), "院校宣讲");
  assert.equal(messageTypeLabel("quality"), "数据质量");
  // 历史消息里的旧取值仍能正确展示
  assert.equal(messageTypeLabel("notice"), "政策公告");
  assert.equal(messageTypeLabel("data_quality"), "数据质量");
  assert.equal(messageTypeLabel(""), "系统消息");
  assert.equal(messageTypeLabel("custom"), "custom");
  assert.deepEqual(
    [...NOTICE_CATEGORY_FALLBACK],
    ["招生政策", "志愿填报", "数据公告", "院校宣讲"],
  );
});
