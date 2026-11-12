import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

function moduleFrom(file) {
  const code = ts.transpileModule(
    readFileSync(new URL(file, import.meta.url), "utf8"),
    { compilerOptions: { module: ts.ModuleKind.CommonJS } },
  ).outputText;
  const loaded = {};
  new Function("require", "exports", code)(() => ({}), loaded);
  return loaded;
}

function school(id, name, extra = {}) {
  return {
    id,
    name,
    region: "浙江",
    city: "杭州",
    group_count: 2,
    location: {
      longitude: 120 + id,
      latitude: 30 + id,
      precision: "university",
      label: "参考位置",
    },
    ...extra,
  };
}

test("schoolPoints 过滤无坐标院校并给选中项放大/换色", () => {
  const { schoolPoints } = moduleFrom("../src/utils/schematicMap.ts");
  const points = schoolPoints(
    [school(1, "浙江大学"), school(2, "未知学院", { location: null }), school(3, "复旦大学")],
    3,
  );
  assert.equal(points.length, 2);
  assert.deepEqual(
    points.map((point) => point.schoolId),
    [1, 3],
  );
  assert.deepEqual(points[1].value, [123, 33]);
  const selected = points.find((point) => point.schoolId === 3);
  const normal = points.find((point) => point.schoolId === 1);
  assert.equal(selected.label.show, true);
  assert.equal(selected.label.formatter, "复旦大学");
  assert.ok(selected.symbolSize > normal.symbolSize);
  assert.notEqual(selected.itemStyle.color, normal.itemStyle.color);
});

test("buildSchematicOption 使用内置底图并保持零外部依赖", () => {
  const { buildSchematicOption, CHINA_MAP_NAME } = moduleFrom(
    "../src/utils/schematicMap.ts",
  );
  const option = buildSchematicOption([school(1, "浙江大学")], null);
  assert.equal(option.geo.map, CHINA_MAP_NAME);
  assert.equal(option.geo.roam, true);
  assert.equal(option.series.length, 1);
  assert.equal(option.series[0].type, "scatter");
  assert.equal(option.series[0].coordinateSystem, "geo");
  assert.equal(option.series[0].data.length, 1);
  assert.doesNotMatch(JSON.stringify(option), /tianditu|openstreetmap|arcgisonline/i);
  const tooltip = option.tooltip.formatter({ data: option.series[0].data[0] });
  assert.match(tooltip, /浙江大学/);
  assert.match(tooltip, /浙江 · 杭州/);
  assert.doesNotMatch(tooltip, /\d+\.\d{3,}/);
  const empty = buildSchematicOption([school(2, "无坐标", { location: null })], null);
  assert.equal(empty.series[0].data.length, 0);
});

test("focusView 只对有坐标的选中院校返回视图", () => {
  const { focusView } = moduleFrom("../src/utils/schematicMap.ts");
  const schools = [school(1, "浙江大学"), school(2, "无坐标", { location: null })];
  assert.deepEqual(focusView(schools, 1), { center: [121, 31], zoom: 5 });
  assert.equal(focusView(schools, 2), undefined);
  assert.equal(focusView(schools, null), undefined);
  assert.equal(focusView(schools, 99), undefined);
});
