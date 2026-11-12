/**
 * 无 Key 的院校分布示意图（ECharts geo）：
 * - 底图是内置的中国省级行政区划 GeoJSON（阿里云 DataV GeoAtlas 公开数据，仅用于位置示意）；
 * - 点位是院校参考坐标（WGS84），不请求任何第三方地图 SDK / 瓦片服务；
 * - 支持鼠标滚轮缩放、拖动平移（geo.roam），点击点位选中院校。
 *
 * 纯函数便于 node 测试：不依赖 DOM / ECharts 实例。
 */
import type { CatalogUniversity } from "../api/types";

export const CHINA_MAP_NAME = "sunpath-china";
export const MAP_ATTRIBUTION = "底图：阿里云 DataV GeoAtlas（仅位置示意）";

export interface SchematicSchoolPoint {
  name: string;
  value: [number, number];
  schoolId: number;
  region: string;
  city: string;
  symbolSize: number;
  itemStyle: { color: string; borderColor: string; borderWidth: number };
  label: { show: boolean; formatter?: string; position?: string; color?: string; fontSize?: number };
}

export interface SchematicMapOption {
  backgroundColor: string;
  tooltip: {
    trigger: string;
    confine: boolean;
    formatter: (params: { data?: SchematicSchoolPoint; name?: string }) => string;
  };
  geo: {
    map: string;
    roam: boolean;
    zoom: number;
    center: [number, number];
    label: { show: boolean };
    itemStyle: { areaColor: string; borderColor: string; borderWidth: number };
    emphasis: {
      label: { show: boolean };
      itemStyle: { areaColor: string };
    };
    select: { disabled: boolean };
  };
  series: {
    id: string;
    type: string;
    coordinateSystem: string;
    symbol: string;
    data: SchematicSchoolPoint[];
    emphasis: { scale: number };
    zlevel: number;
  }[];
}

const SELECTED_COLOR = "#d98c2b";
const NORMAL_COLOR = "#2f6fb0";

/** 院校 → 地图点位；selectedId 对应点位加大并显示名称。 */
export function schoolPoints(
  schools: CatalogUniversity[],
  selectedId: number | null,
): SchematicSchoolPoint[] {
  return schools
    .filter((school) => school.location)
    .map((school) => {
      const selected = school.id === selectedId;
      const count = school.group_count || 0;
      return {
        name: school.name,
        value: [school.location!.longitude, school.location!.latitude] as [number, number],
        schoolId: school.id,
        region: school.region,
        city: school.city,
        symbolSize: selected ? 16 : Math.min(9 + count * 2, 14),
        itemStyle: {
          color: selected ? SELECTED_COLOR : NORMAL_COLOR,
          borderColor: "#ffffff",
          borderWidth: 2,
        },
        label: selected
          ? {
              show: true,
              formatter: school.name,
              position: "right",
              color: "#1f3a56",
              fontSize: 12,
            }
          : { show: false },
      };
    });
}

export function buildSchematicOption(
  schools: CatalogUniversity[],
  selectedId: number | null,
  view?: { center?: [number, number]; zoom?: number },
): SchematicMapOption {
  return {
    backgroundColor: "#f4f8fc",
    tooltip: {
      trigger: "item",
      confine: true,
      // 只展示院校名与所在地区，不暴露原始经纬度
      formatter: (params) => {
        const point = params.data;
        if (!point) return params.name ?? "";
        const region = point.city ? `${point.region} · ${point.city}` : point.region;
        return `<strong>${point.name}</strong><br/>${region}`;
      },
    },
    geo: {
      map: CHINA_MAP_NAME,
      roam: true,
      zoom: view?.zoom ?? 1.2,
      center: view?.center ?? [104, 35.5],
      label: { show: false },
      itemStyle: { areaColor: "#e9f1f9", borderColor: "#c3d5e6", borderWidth: 0.6 },
      emphasis: { label: { show: false }, itemStyle: { areaColor: "#dbe8f6" } },
      select: { disabled: true },
    },
    series: [
      {
        id: "schools",
        type: "scatter",
        coordinateSystem: "geo",
        symbol: "circle",
        data: schoolPoints(schools, selectedId),
        emphasis: { scale: 1.3 },
        zlevel: 2,
      },
    ],
  };
}

/** 选中院校时把视图聚焦到该点；没有选中返回 undefined（保持用户当前的平移缩放）。 */
export function focusView(
  schools: CatalogUniversity[],
  selectedId: number | null,
): { center: [number, number]; zoom: number } | undefined {
  const school = schools.find((item) => item.id === selectedId && item.location);
  if (!school?.location) return undefined;
  return {
    center: [school.location.longitude, school.location.latitude],
    // 保持省级底图的上下文：过大的缩放会让示意底图只剩空白背景
    zoom: 5,
  };
}
