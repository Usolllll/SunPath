import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

// Exercise the real-data display helpers with the production source (no extra toolchain).
const source = readFileSync(
  new URL("../src/utils/realdata.ts", import.meta.url),
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
const { coverageText, officialCheckText, safeSourceUrl, yearSpan } = exports;

const summary = {
  total_rows: 142531,
  provinces: [
    { province: "黑龙江", rows: 2254, schools: 312, years: [2024, 2026] },
    { province: "贵州", rows: 72119, schools: 1178, years: [2024, 2025, 2026] },
    {
      province: "辽宁",
      rows: 68158,
      schools: 1041,
      years: [2023, 2024, 2025, 2026],
    },
  ],
};

test("freshness headline lists the three supported provinces in fixed order", () => {
  assert.equal(
    coverageText(summary),
    "覆盖 3 省 / 142,531 条 / 辽宁 2023–2026 · 贵州 2024–2026 · 黑龙江 2024–2026",
  );
});

test("freshness headline degrades gracefully when nothing is imported", () => {
  assert.equal(coverageText(null), "官方投档数据尚未收录");
  assert.equal(coverageText({ total_rows: 0, provinces: [] }), "官方投档数据尚未收录");
});

test("year span sorts years and never invents missing data", () => {
  assert.equal(yearSpan([2026, 2023, 2024, 2025]), "2023–2026");
  assert.equal(yearSpan([2026]), "2026");
  assert.equal(yearSpan([]), "年份未标注");
  assert.equal(yearSpan(null), "年份未标注");
});

test("official check text keeps year, rank and subject type", () => {
  assert.equal(
    officialCheckText({ exam_year: 2026, min_rank: 1235, subject_type: "历史类" }),
    "官方 2026 投档最低位次 1,235（历史类）",
  );
  assert.equal(
    officialCheckText({ exam_year: 2025, min_rank: null }),
    "官方 2025 年投档记录（最低位次未收录）",
  );
  assert.equal(officialCheckText(null), null);
  assert.equal(officialCheckText({ min_rank: 1235 }), null);
  assert.equal(officialCheckText({ min_rank: 1235, exam_year: 0 }), null);
});

test("source links only accept http(s), so javascript/data URLs are dropped", () => {
  assert.equal(
    safeSourceUrl("https://www.lnzsks.com/newsinfo/IMS_20260721_46231.htm"),
    "https://www.lnzsks.com/newsinfo/IMS_20260721_46231.htm",
  );
  assert.equal(
    safeSourceUrl("http://zsksy.guizhou.gov.cn/ygpt/tdqk/202407/t20240723_85148150.html"),
    "http://zsksy.guizhou.gov.cn/ygpt/tdqk/202407/t20240723_85148150.html",
  );
  for (const bad of [
    null,
    "",
    "  ",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "//evil.example/x",
  ])
    assert.equal(safeSourceUrl(bad), null, String(bad));
});
