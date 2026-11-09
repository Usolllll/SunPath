import type { CatalogUniversity } from "../api/types";
import type { Tianditu, TMap, TMarker } from "./tianditu";

function escape(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
}

export function createUniversityMap(
  T: Tianditu,
  container: string,
  onSelect: (id: number) => void,
) {
  // Default official basemap, labels and copyright controls are preserved.
  const map: TMap = new T.Map(container, { minZoom: 3, maxZoom: 18 });
  map.centerAndZoom(new T.LngLat(105, 35), 4);
  map.disableScrollWheelZoom();
  map.addControl(new T.Control.Zoom());
  map.addControl(new T.Control.Scale());
  let schools: CatalogUniversity[] = [];
  const markers = new Map<number, TMarker>();
  const clusterSvg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><circle cx="20" cy="20" r="19" fill="#c3dbed"/><circle cx="20" cy="20" r="15" fill="#326fa9"/></svg>';
  const clusters = new T.MarkerClusterer(map, {
    markers: [],
    maxZoom: 11,
    styles: [
      {
        url:
          "data:image/svg+xml;charset=utf-8," + encodeURIComponent(clusterSvg),
        size: [40, 40],
        offset: new T.Point(20, 20),
        textColor: "#ffffff",
        textSize: 12,
        range: [0, 100000],
      },
    ],
  });

  function icon(active: boolean, city: boolean) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30"><circle cx="15" cy="15" r="${active ? 11 : 8}" fill="${active ? "#dc9b40" : city ? "#ffffff" : "#397cc9"}" stroke="${city && !active ? "#657c94" : "#ffffff"}" stroke-width="3" ${city && !active ? 'stroke-dasharray="3 2"' : ""}/></svg>`;
    return new T.Icon({
      iconUrl: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg),
      iconSize: new T.Point(30, 30),
      iconAnchor: new T.Point(15, 15),
    });
  }
  function points() {
    return schools
      .filter((s) => s.location)
      .map((s) => new T.LngLat(s.location!.longitude, s.location!.latitude));
  }
  function fit() {
    const positions = points();
    map.closeInfoWindow();
    if (!positions.length) map.centerAndZoom(new T.LngLat(105, 35), 4);
    else {
      // Add view padding only, never fake markers, so points do not obscure the
      // official copyright/approval strip along the bottom of the SDK canvas.
      const coordinates = schools.flatMap((s) =>
        s.location ? [s.location] : [],
      );
      if (coordinates.length > 1) {
        const lngs = coordinates.map((p) => p.longitude);
        const lats = coordinates.map((p) => p.latitude);
        positions.push(
          new T.LngLat(Math.min(...lngs) - 2, Math.min(...lats) - 2.5),
          new T.LngLat(Math.max(...lngs) + 2, Math.max(...lats) + 2.5),
        );
      }
      const viewport = map.getViewport(positions);
      map.centerAndZoom(viewport.center, Math.min(viewport.zoom, 12));
    }
  }
  function select(id: number | null) {
    markers.forEach((marker, key) =>
      marker.setIcon(
        icon(
          key === id,
          schools.find((s) => s.id === key)?.location?.precision === "city",
        ),
      ),
    );
    const school = schools.find((s) => s.id === id);
    const marker = id === null ? undefined : markers.get(id);
    if (!marker || !school) {
      map.closeInfoWindow();
      return;
    }
    // Above the cluster maximum zoom, each actual university marker is visible.
    map.panTo(marker.getLngLat(), Math.max(map.getZoom(), 12));
    marker.openInfoWindow(
      new T.InfoWindow(
        `<div class="university-map-info"><strong>${escape(school.name)}</strong><p>${escape(school.region)} · ${escape(school.city)} · ${school.group_count} 个专业组</p><p>${escape(school.location!.label)}</p></div>`,
      ),
    );
  }
  function update(value: CatalogUniversity[], selectedId: number | null) {
    schools = value;
    clusters.clearMarkers();
    markers.clear();
    for (const school of schools.filter((s) => s.location)) {
      const point = new T.LngLat(
        school.location!.longitude,
        school.location!.latitude,
      );
      const marker = new T.Marker(point, {
        icon: icon(
          school.id === selectedId,
          school.location!.precision === "city",
        ),
        title: school.name,
      });
      marker.addEventListener("click", () => onSelect(school.id));
      markers.set(school.id, marker);
    }
    clusters.addMarkers([...markers.values()]);
    fit();
  }
  return {
    update,
    select,
    fit,
    resize() {
      map.checkResize();
    },
    destroy() {
      clusters.clearMarkers();
      markers.clear();
      map.closeInfoWindow();
      map.clearOverLays();
      map.remove?.();
    },
  };
}
