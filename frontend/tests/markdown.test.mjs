import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

// Exercise the production renderer without introducing a second test toolchain.
const source = readFileSync(
  new URL("../src/utils/markdown.ts", import.meta.url),
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
const { renderMarkdown } = exports;

test("renders actual model formatting, paragraphs and tables", () => {
  const html = renderMarkdown(
    "## 建议\n\n**稳妥优先**\n\n1. 第一项\n2. 第二项\n\n|方案|位次|\n|---|---|\n|A|22580|\n\n```text\n示例\n```\n",
  );
  for (const fragment of [
    "<h2>建议</h2>",
    "<strong>稳妥优先</strong>",
    "<ol>",
    "<li>第一项</li>",
    "<table>",
    "<pre><code",
  ])
    assert.ok(html.includes(fragment), fragment);
});

test("escapes HTML, refuses unsafe URLs and blocks external images", () => {
  const html = renderMarkdown(
    "<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))\n\n![private](https://example.com/tracker.png)\n\n[官网](https://example.com)",
  );
  assert.ok(!html.includes("<script"));
  assert.ok(!html.includes("<img"));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(!html.includes("tracker.png"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes('rel="noopener noreferrer"'));
  assert.ok(html.includes('referrerpolicy="no-referrer"'));
});
