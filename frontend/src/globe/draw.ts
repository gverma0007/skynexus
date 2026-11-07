// Line-art globe rendering on a 2D canvas (d3-geo orthographic projection).
import { geoArea, geoContains, geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo';
import type { GeoPermissibleObjects, GeoProjection } from 'd3-geo';
import type { Feature, MultiLineString, MultiPolygon, Polygon } from 'geojson';
import { feature, mesh } from 'topojson-client';
import type { Topology } from 'topojson-specification';

export interface Atlas {
  land: Feature<MultiPolygon | Polygon> | GeoPermissibleObjects;
  borders: MultiLineString;
}

export interface GlobeRegion {
  id: string;
  name: string;
  lat: number;
  lon: number;
  score: number;
  level: 0 | 1 | 2 | 3;
  polygon: Polygon;
}

export interface GlobePoint {
  lat: number;
  lon: number;
}
export interface GlobeFlight extends GlobePoint {
  id: string;
  heading: number;
  label: string;
}
export interface GlobeSat extends GlobePoint {
  id: number;
  label: string;
}
export interface GlobeEvent extends GlobePoint {
  id: string;
  mag: number;
  label: string;
}

export interface Layers {
  aircraft: boolean;
  satellites: boolean;
  events: boolean;
  outlines: boolean;
}

export interface DrawInput {
  atlas: Atlas | null;
  rotate: [number, number];
  zoom: number;
  regions: GlobeRegion[];
  flights: GlobeFlight[];
  sats: GlobeSat[];
  events: GlobeEvent[];
  layers: Layers;
  selectedRegion: string | null;
  selectedSat: number | null;
  hoverRegion: string | null;
}

export const COLORS = {
  ink: '#000000',
  ink2: '#5C5C5C',
  ink3: '#8C8C88',
  land: '#F2F2EF',
  grid: '#EAEAE7',
  border: '#BDBDB9',
  signal: '#E5484D',
};

const REGION_FILL = ['rgba(0,0,0,0)', 'rgba(0,0,0,0.07)', 'rgba(0,0,0,0.2)', 'rgba(229,72,77,0.2)'];

export function prepareAtlas(topo: Topology): Atlas {
  const objects = topo.objects as Record<string, never>;
  return {
    land: feature(topo, objects.land) as unknown as Feature<MultiPolygon>,
    borders: mesh(topo, objects.countries, (a, b) => a !== b),
  };
}

/** Build a densified polygon so straight lon/lat box edges follow parallels. */
export function ringToPolygon(ring: [number, number][]): Polygon {
  const lonlat = ring.map(([lat, lon]) => [lon, lat] as [number, number]);
  const dense: [number, number][] = [];
  for (let i = 0; i < lonlat.length - 1; i++) {
    const [a, b] = [lonlat[i], lonlat[i + 1]];
    let dl = b[0] - a[0];
    if (dl > 180) dl -= 360;
    if (dl < -180) dl += 360;
    const n = Math.max(1, Math.ceil(Math.max(Math.abs(dl), Math.abs(b[1] - a[1])) / 2));
    for (let k = 0; k < n; k++) dense.push([a[0] + (dl * k) / n, a[1] + ((b[1] - a[1]) * k) / n]);
  }
  dense.push(lonlat[lonlat.length - 1]);
  let poly: Polygon = { type: 'Polygon', coordinates: [dense] };
  // d3 treats rings by winding: if this one covers more than a hemisphere, flip it.
  if (geoArea(poly) > 2 * Math.PI) poly = { type: 'Polygon', coordinates: [[...dense].reverse()] };
  return poly;
}

export function makeProjection(w: number, h: number, rotate: [number, number], zoom: number): GeoProjection {
  const r = (Math.min(w, h) / 2 - 18) * zoom;
  return geoOrthographic().translate([w / 2, h / 2]).scale(r).rotate([rotate[0], rotate[1], 0]).clipAngle(90);
}

export function isVisible(rotate: [number, number], lon: number, lat: number): boolean {
  return geoDistance([lon, lat], [-rotate[0], -rotate[1]]) < Math.PI / 2 - 0.01;
}

export function draw(ctx: CanvasRenderingContext2D, w: number, h: number, d: DrawInput): GeoProjection {
  const proj = makeProjection(w, h, d.rotate, d.zoom);
  const path = geoPath(proj, ctx);
  ctx.clearRect(0, 0, w, h);

  ctx.beginPath();
  path({ type: 'Sphere' });
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();

  ctx.beginPath();
  path(geoGraticule10());
  ctx.lineWidth = 0.5;
  ctx.strokeStyle = COLORS.grid;
  ctx.stroke();

  if (d.atlas) {
    ctx.beginPath();
    path(d.atlas.land as GeoPermissibleObjects);
    ctx.fillStyle = COLORS.land;
    ctx.fill();
    ctx.lineWidth = 0.8;
    ctx.strokeStyle = '#1A1A1A';
    ctx.stroke();
    ctx.beginPath();
    path(d.atlas.borders);
    ctx.lineWidth = 0.4;
    ctx.strokeStyle = COLORS.border;
    ctx.stroke();
  }

  // Regions: ink density = severity
  if (d.layers.outlines) {
    for (const reg of d.regions) {
      const sel = reg.id === d.selectedRegion;
      const hover = reg.id === d.hoverRegion;
      ctx.beginPath();
      path(reg.polygon);
      if (reg.level > 0 || hover || sel) {
        ctx.fillStyle = reg.level > 0 ? REGION_FILL[reg.level] : 'rgba(0,0,0,0.04)';
        ctx.fill();
      }
      ctx.setLineDash(reg.level === 0 && !sel ? [3, 3] : []);
      ctx.lineWidth = sel ? 2.2 : hover ? 1.6 : reg.level === 3 ? 1.4 : 0.9;
      ctx.strokeStyle = reg.level === 3 ? COLORS.signal : COLORS.ink;
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // Aircraft: short ticks along heading
  if (d.layers.aircraft) {
    ctx.strokeStyle = COLORS.ink;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const f of d.flights) {
      if (!isVisible(d.rotate, f.lon, f.lat)) continue;
      const p = proj([f.lon, f.lat]);
      if (!p) continue;
      const a = ((f.heading - 90) * Math.PI) / 180;
      const dx = Math.cos(a) * 3;
      const dy = Math.sin(a) * 3;
      ctx.moveTo(p[0] - dx, p[1] - dy);
      ctx.lineTo(p[0] + dx, p[1] + dy);
    }
    ctx.stroke();
  }

  // Satellites: hollow rings
  if (d.layers.satellites) {
    ctx.lineWidth = 0.9;
    ctx.strokeStyle = COLORS.ink2;
    ctx.beginPath();
    for (const s of d.sats) {
      if (s.id === d.selectedSat || !isVisible(d.rotate, s.lon, s.lat)) continue;
      const p = proj([s.lon, s.lat]);
      if (!p) continue;
      ctx.moveTo(p[0] + 2.3, p[1]);
      ctx.arc(p[0], p[1], 2.3, 0, Math.PI * 2);
    }
    ctx.stroke();
    const sel = d.sats.find((s) => s.id === d.selectedSat);
    if (sel && isVisible(d.rotate, sel.lon, sel.lat)) {
      const p = proj([sel.lon, sel.lat]);
      if (p) {
        ctx.beginPath();
        ctx.arc(p[0], p[1], 5, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.ink;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(p[0], p[1], 9, 0, Math.PI * 2);
        ctx.lineWidth = 1.4;
        ctx.strokeStyle = COLORS.ink;
        ctx.stroke();
      }
    }
  }

  // Conflict & security threats: diamonds sized by severity
  if (d.layers.events) {
    for (const e of d.events) {
      if (!isVisible(d.rotate, e.lon, e.lat)) continue;
      const p = proj([e.lon, e.lat]);
      if (!p) continue;
      const s = Math.max(2.5, 2 + (e.mag - 2.5) * 1.4);
      ctx.beginPath();
      ctx.moveTo(p[0], p[1] - s);
      ctx.lineTo(p[0] + s, p[1]);
      ctx.lineTo(p[0], p[1] + s);
      ctx.lineTo(p[0] - s, p[1]);
      ctx.closePath();
      ctx.fillStyle = e.mag >= 5.5 ? COLORS.signal : COLORS.ink;
      ctx.fill();
    }
  }

  // Outline of the sphere on top
  ctx.beginPath();
  path({ type: 'Sphere' });
  ctx.lineWidth = 1.25;
  ctx.strokeStyle = COLORS.ink;
  ctx.stroke();

  // Labels for notable or selected regions
  if (d.layers.outlines) {
    ctx.font = '500 11px "Geist Variable", system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (const reg of d.regions) {
      const sel = reg.id === d.selectedRegion;
      if (reg.level < 1 && !sel && reg.id !== d.hoverRegion) continue;
      if (!isVisible(d.rotate, reg.lon, reg.lat)) continue;
      const p = proj([reg.lon, reg.lat]);
      if (!p) continue;
      const label = `${reg.name}  ${Math.round(reg.score)}`;
      const tw = ctx.measureText(label).width + 14;
      roundRect(ctx, p[0] - tw / 2, p[1] - 10, tw, 20, 10);
      ctx.fillStyle = sel ? COLORS.ink : '#FFFFFF';
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = reg.level === 3 && !sel ? COLORS.signal : COLORS.ink;
      ctx.stroke();
      ctx.fillStyle = sel ? '#FFFFFF' : COLORS.ink;
      ctx.fillText(label, p[0], p[1] + 0.5);
    }
  }
  return proj;
}

export function regionAt(proj: GeoProjection, regions: GlobeRegion[], x: number, y: number): GlobeRegion | null {
  const ll = proj.invert?.([x, y]);
  if (!ll || Number.isNaN(ll[0])) return null;
  // smallest containing region wins (zones overlap)
  let best: GlobeRegion | null = null;
  let bestArea = Infinity;
  for (const r of regions) {
    if (geoContains(r.polygon, ll)) {
      const a = geoArea(r.polygon);
      if (a < bestArea) {
        best = r;
        bestArea = a;
      }
    }
  }
  return best;
}

export function nearest<T extends GlobePoint>(
  proj: GeoProjection, rotate: [number, number], items: T[], x: number, y: number, maxPx: number,
): T | null {
  let best: T | null = null;
  let bestD = maxPx * maxPx;
  for (const it of items) {
    if (!isVisible(rotate, it.lon, it.lat)) continue;
    const p = proj([it.lon, it.lat]);
    if (!p) continue;
    const dd = (p[0] - x) ** 2 + (p[1] - y) ** 2;
    if (dd < bestD) {
      bestD = dd;
      best = it;
    }
  }
  return best;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
