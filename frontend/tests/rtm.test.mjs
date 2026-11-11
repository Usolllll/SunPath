import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(
  new URL("../src/utils/rtm.ts", import.meta.url),
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
  PLAN_BATCHES,
  SUBMIT_LOCK_MESSAGE,
  clearedSubmitKey,
  hasId,
  idempotencySignature,
  isPlanEditable,
  isValidSubmitKey,
  patrolCheckedText,
  planBatchLabel,
  planStatusLabel,
  submitKeyFor,
  toggleId,
} = exports;

test("plan batch defaults to 本科批 and rejects unknown values", () => {
  assert.deepEqual(PLAN_BATCHES, ["本科批", "专科批"]);
  assert.equal(planBatchLabel("本科批"), "本科批");
  assert.equal(planBatchLabel("专科批"), "专科批");
  assert.equal(planBatchLabel(undefined), "本科批");
  assert.equal(planBatchLabel("提前批"), "本科批");
});

test("only drafts are editable and submitted plans tell the user to withdraw first", () => {
  assert.equal(planStatusLabel("draft"), "草稿");
  assert.equal(planStatusLabel("submitted"), "已提交");
  assert.equal(planStatusLabel(undefined), "草稿");
  assert.equal(isPlanEditable("draft"), true);
  assert.equal(isPlanEditable(undefined), true);
  assert.equal(isPlanEditable("submitted"), false);
  assert.equal(SUBMIT_LOCK_MESSAGE, "已提交的方案不可编辑，请先撤回");
});

test("favorite ids toggle immutably", () => {
  const ids = [3, 7];
  const added = toggleId(ids, 5);
  assert.deepEqual(added, [3, 7, 5]);
  assert.deepEqual(ids, [3, 7], "原始数组不应被修改");
  const removed = toggleId(added, 7);
  assert.deepEqual(removed, [3, 5]);
  assert.deepEqual(toggleId([], 1), [1]);
  assert.equal(hasId(ids, 7), true);
  assert.equal(hasId(ids, 8), false);
});

test("idempotency signature identifies the same draft, ignoring name padding", () => {
  const base = { planId: 12, name: "我的方案", batch: "本科批", itemIds: [4, 2, 9] };
  const signature = idempotencySignature(base);
  assert.equal(
    signature,
    idempotencySignature({ ...base, name: " 我的方案 " }),
    "名称首尾空格不影响同一草稿",
  );
  assert.notEqual(signature, idempotencySignature({ ...base, itemIds: [2, 4, 9] }));
  assert.notEqual(signature, idempotencySignature({ ...base, batch: "专科批" }));
  assert.notEqual(signature, idempotencySignature({ ...base, planId: 13 }));
  assert.equal(
    idempotencySignature({ ...base, planId: undefined }),
    "draft|我的方案|本科批|4,2,9",
  );
});

test("submit key is reused for the same draft and regenerated after changes or success", () => {
  let generated = 0;
  const generate = () => `key-${++generated}`;
  const first = submitKeyFor("sig-a", clearedSubmitKey(), generate);
  assert.deepEqual(first, { signature: "sig-a", key: "key-1" });
  const retry = submitKeyFor("sig-a", first, generate);
  assert.equal(retry.key, "key-1", "同一草稿重试必须复用 key");
  const changed = submitKeyFor("sig-b", retry, generate);
  assert.deepEqual(changed, { signature: "sig-b", key: "key-2" });
  const afterSuccess = submitKeyFor("sig-b", clearedSubmitKey(), generate);
  assert.equal(afterSuccess.key, "key-3", "提交成功后清空，下次生成新 key");
});

test("idempotency key matches backend 1–64 visible ASCII constraint", () => {
  assert.equal(isValidSubmitKey("a"), true);
  assert.equal(isValidSubmitKey("1b7c0f1e-2a3b-4c5d-8e9f-0a1b2c3d4e5f"), true);
  assert.equal(isValidSubmitKey("a".repeat(64)), true);
  assert.equal(isValidSubmitKey("a".repeat(65)), false);
  assert.equal(isValidSubmitKey(""), false);
  assert.equal(isValidSubmitKey("含中文"), false);
  assert.equal(isValidSubmitKey("with space"), false);
});

test("patrol timestamps accept compact report names and ISO strings", () => {
  assert.equal(patrolCheckedText("20261110_153319"), "2026-11-10 15:33");
  assert.equal(patrolCheckedText("2026-11-10T15:32:56+08:00"), "2026-11-10T15:32:56+08:00");
  assert.equal(patrolCheckedText(""), "未标注");
  assert.equal(patrolCheckedText(null), "未标注");
  assert.equal(patrolCheckedText(undefined), "未标注");
});
