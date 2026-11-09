/** The only allowed map SDK is Tianditu's official HTTPS JS API. */
export interface TPoint {
  lng: number;
  lat: number;
}
interface TIcon {}
interface TInfoWindow {}
interface TControl {}
export interface TMarker {
  getLngLat(): TPoint;
  setIcon(icon: TIcon): void;
  addEventListener(event: string, handler: () => void): void;
  openInfoWindow(info: TInfoWindow): void;
}
export interface TMap {
  centerAndZoom(point: TPoint, zoom: number): void;
  getViewport(points: TPoint[]): { center: TPoint; zoom: number };
  getZoom(): number;
  panTo(point: TPoint, zoom?: number): void;
  checkResize(): void;
  clearOverLays(): void;
  addControl(control: TControl): void;
  disableScrollWheelZoom(): void;
  closeInfoWindow(): void;
  remove?(): void;
}
export interface TCluster {
  clearMarkers(): void;
  addMarkers(markers: TMarker[]): void;
}
export interface Tianditu {
  Map: new (
    container: string,
    options: { minZoom: number; maxZoom: number },
  ) => TMap;
  LngLat: new (longitude: number, latitude: number) => TPoint;
  Point: new (x: number, y: number) => object;
  Icon: new (options: {
    iconUrl: string;
    iconSize: object;
    iconAnchor: object;
  }) => TIcon;
  Marker: new (
    point: TPoint,
    options: { icon: TIcon; title: string },
  ) => TMarker;
  MarkerClusterer: new (
    map: TMap,
    options: { markers: TMarker[]; maxZoom: number; styles: object[] },
  ) => TCluster;
  InfoWindow: new (content: string) => TInfoWindow;
  Control: { Zoom: new () => TControl; Scale: new () => TControl };
}

let pending: Promise<Tianditu> | undefined;

export function hasTiandituKey(key: string): boolean {
  return /^[a-f\d]{32}$/i.test(key.trim());
}

export function loadTianditu(
  key: string,
  timeoutMs = 20_000,
): Promise<Tianditu> {
  const token = key.trim();
  if (!hasTiandituKey(token))
    return Promise.reject(
      new Error("地图服务尚未启用，请配置有效的天地图 Web 端 Key。"),
    );
  const global = window as Window & { T?: Tianditu };
  if (global.T?.MarkerClusterer) return Promise.resolve(global.T);
  if (pending) return pending;
  pending = new Promise<Tianditu>((resolve, reject) => {
    const script = document.createElement("script");
    let poll: ReturnType<typeof setInterval> | undefined;
    const timeout = setTimeout(() => finish(false), timeoutMs);
    function finish(ok: boolean) {
      clearTimeout(timeout);
      clearInterval(poll);
      script.onload = script.onerror = null;
      if (ok && global.T?.Map && global.T.MarkerClusterer) resolve(global.T);
      else {
        script.remove();
        reject(
          new Error("天地图加载失败，请检查网络、Key 权限和域名白名单后重试。"),
        );
      }
    }
    script.id = "sunpath-tianditu-sdk";
    script.async = true;
    script.src = `https://api.tianditu.gov.cn/api?v=4.0&tk=${encodeURIComponent(token)}`;
    // The official bootstrap loads its components separately. Its own onload
    // does not mean MarkerClusterer, Icon and InfoWindow are already available.
    script.onload = () => {
      const ready = () => {
        if (
          global.T?.Map &&
          global.T.MarkerClusterer &&
          global.T.Marker &&
          global.T.Icon &&
          global.T.InfoWindow &&
          global.T.Control?.Zoom &&
          global.T.Control.Scale
        )
          finish(true);
      };
      poll = setInterval(ready, 50);
      ready();
    };
    script.onerror = () => finish(false);
    document.head.appendChild(script);
  }).catch((error) => {
    pending = undefined;
    throw error;
  });
  return pending;
}
