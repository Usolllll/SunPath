import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { test } from "node:test";
import ts from "typescript";

function moduleFrom(file) {
  const code = ts.transpileModule(
    readFileSync(new URL(file, import.meta.url), "utf8"),
    { compilerOptions: { module: ts.ModuleKind.CommonJS } },
  ).outputText;
  const result = {};
  new Function("require", "exports", code)(
    createRequire(import.meta.url),
    result,
  );
  return result;
}
function sdkDocument() {
  const scripts = [];
  globalThis.window = {};
  globalThis.document = {
    createElement() {
      return {
        remove() {
          this.removed = true;
        },
      };
    },
    head: {
      appendChild(script) {
        scripts.push(script);
      },
    },
  };
  return scripts;
}
const fakeKey = "a".repeat(32);
function readySdk() {
  return {
    Map: class {},
    MarkerClusterer: class {},
    Marker: class {},
    Icon: class {},
    InfoWindow: class {},
    Control: { Zoom: class {}, Scale: class {} },
  };
}

test("no key or placeholder never requests a map or falls back to foreign tiles", async () => {
  const scripts = sdkDocument();
  const { loadTianditu, hasTiandituKey } = moduleFrom(
    "../src/utils/tianditu.ts",
  );
  for (const value of ["", "YOUR_TIANDITU_WEB_KEY", "https://tile.invalid"]) {
    assert.equal(hasTiandituKey(value), false);
    await assert.rejects(loadTianditu(value));
  }
  assert.equal(scripts.length, 0);
});

test("official HTTPS loader shares requests and waits for separately loaded SDK components", async () => {
  const scripts = sdkDocument();
  const { loadTianditu } = moduleFrom("../src/utils/tianditu.ts");
  const first = loadTianditu(fakeKey, 1000);
  assert.equal(first, loadTianditu(fakeKey, 1000));
  const url = new URL(scripts[0].src);
  assert.equal(url.origin, "https://api.tianditu.gov.cn");
  assert.equal(url.pathname, "/api");
  assert.equal(url.searchParams.get("v"), "4.0");
  globalThis.window.T = { Map: class {} };
  scripts[0].onload();
  let resolved = false;
  first.then(() => {
    resolved = true;
  });
  await new Promise((resolve) => setTimeout(resolve, 70));
  assert.equal(resolved, false);
  globalThis.window.T = readySdk();
  assert.equal(await first, globalThis.window.T);
  assert.equal(scripts.length, 1);
});

test("SDK network error and timeout remove failed scripts and permit retry without exposing key", async () => {
  const scripts = sdkDocument();
  const { loadTianditu } = moduleFrom("../src/utils/tianditu.ts");
  const first = loadTianditu(fakeKey, 1000);
  scripts[0].onerror();
  await assert.rejects(first, (error) => !error.message.includes(fakeKey));
  assert.equal(scripts[0].removed, true);
  const retry = loadTianditu(fakeKey, 15);
  await assert.rejects(retry, (error) => !error.message.includes(fakeKey));
  assert.equal(scripts.length, 2);
  assert.equal(scripts[1].removed, true);
  globalThis.window.T = readySdk();
  assert.equal(await loadTianditu(fakeKey), globalThis.window.T);
});

test("map adapter preserves WGS84 order, filters markers, selects schools, escapes labels and keeps SDK base controls", () => {
  const { createUniversityMap } = moduleFrom("../src/utils/universityMap.ts");
  const state = { maps: [], markers: [], info: [], clusters: [] };
  class Point {
    constructor(lng, lat) {
      this.lng = lng;
      this.lat = lat;
    }
  }
  class FakeMap {
    constructor(container, options) {
      this.container = container;
      this.options = options;
      this.controls = [];
      state.maps.push(this);
    }
    centerAndZoom(point, zoom) {
      this.center = point;
      this.zoom = zoom;
    }
    getViewport(points) {
      this.points = points;
      return { center: points[0], zoom: 16 };
    }
    getZoom() {
      return this.zoom;
    }
    panTo(point, zoom) {
      this.center = point;
      this.zoom = zoom;
    }
    addControl(value) {
      this.controls.push(value);
    }
    disableScrollWheelZoom() {}
    closeInfoWindow() {}
    checkResize() {
      this.resized = true;
    }
    clearOverLays() {
      this.cleared = true;
    }
    remove() {
      this.removed = true;
    }
  }
  class Marker {
    constructor(point, options) {
      this.point = point;
      this.options = options;
      state.markers.push(this);
    }
    getLngLat() {
      return this.point;
    }
    setIcon(icon) {
      this.icon = icon;
    }
    addEventListener(event, handler) {
      this.click = handler;
    }
    openInfoWindow(info) {
      this.info = info;
    }
  }
  class Cluster {
    constructor(map, options) {
      this.options = options;
      this.markers = [];
      state.clusters.push(this);
    }
    clearMarkers() {
      this.markers = [];
    }
    addMarkers(markers) {
      this.markers.push(...markers);
    }
  }
  const T = {
    Map: FakeMap,
    LngLat: Point,
    Point,
    Marker,
    MarkerClusterer: Cluster,
    Icon: class {
      constructor(options) {
        this.options = options;
      }
    },
    InfoWindow: class {
      constructor(content) {
        this.content = content;
        state.info.push(content);
      }
    },
    Control: { Zoom: class {}, Scale: class {} },
  };
  const selected = [];
  const map = createUniversityMap(T, "map", (id) => selected.push(id));
  const school = {
    id: 1,
    name: "<img src=x onerror=alert(1)>",
    region: "浙江",
    city: "杭州",
    group_count: 2,
    location: {
      longitude: 120,
      latitude: 30,
      precision: "university",
      label: "参考位置",
    },
  };
  map.update([school, { ...school, id: 2, location: null }], null);
  assert.equal(state.markers.length, 1);
  assert.deepEqual(state.maps[0].points, [new Point(120, 30)]);
  assert.equal(state.maps[0].zoom, 12);
  assert.equal(state.maps[0].controls.length, 2);
  assert.deepEqual(Object.keys(state.maps[0].options).sort(), [
    "maxZoom",
    "minZoom",
  ]);
  state.markers[0].click();
  assert.deepEqual(selected, [1]);
  map.select(1);
  assert.equal(state.maps[0].center.lng, 120);
  assert.ok(!state.info[0].includes("<img"));
  assert.ok(state.info[0].includes("&lt;img"));
  map.update([], null);
  assert.equal(state.clusters[0].markers.length, 0);
  assert.equal(state.maps[0].zoom, 4);
  map.resize();
  map.destroy();
  assert.equal(state.maps[0].resized, true);
  assert.equal(state.maps[0].removed, true);
});
