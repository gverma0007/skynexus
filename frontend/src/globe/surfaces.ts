import { geoContains, geoPath } from 'd3-geo';
import type { GeoProjection } from 'd3-geo';
import type { Atlas } from './draw';

export type GlobeView = 'line' | 'earth' | 'dots' | 'flat';
const pointCache = new WeakMap<Atlas, [number, number][]>();
let rasterCache: { key: string; canvas: HTMLCanvasElement } | null = null;

export function landPoints(atlas: Atlas): [number, number][] {
  const cached = pointCache.get(atlas);
  if (cached) return cached;
  const points: [number, number][] = [];
  for (let lat = -84; lat <= 84; lat += 2.4) {
    const step = 2.4 / Math.max(0.15, Math.cos(lat * Math.PI / 180));
    for (let lon = -180; lon < 180; lon += step) {
      if (geoContains(atlas.land, [lon, lat])) points.push([lon, lat]);
    }
  }
  pointCache.set(atlas, points);
  return points;
}

export function earthSurface(ctx: CanvasRenderingContext2D, proj: GeoProjection, w: number, h: number, texture: ImageData | null) {
  if (!texture || !proj.invert) return;
  const radius = proj.scale();
  const [cx, cy] = proj.translate();
  const size = Math.min(420, Math.ceil(radius * 2));
  const key = [size, ...proj.rotate().map((n) => Math.round(n * 5)), w, h, texture.width].join(':');
  if (!rasterCache || rasterCache.key !== key) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const off = canvas.getContext('2d');
    if (!off) return;
    const pixels = off.createImageData(size, size);
    const data = pixels.data;
    for (let y = 0; y < size; y++) {
      const ny = (y + 0.5) / size * 2 - 1;
      for (let x = 0; x < size; x++) {
        const nx = (x + 0.5) / size * 2 - 1;
        const square = nx * nx + ny * ny;
        if (square >= 1) continue;
        const ll = proj.invert([cx + nx * radius, cy + ny * radius]);
        if (!ll) continue;
        const tx = Math.min(texture.width - 1, Math.max(0, Math.floor((ll[0] + 180) / 360 * texture.width)));
        const ty = Math.min(texture.height - 1, Math.max(0, Math.floor((90 - ll[1]) / 180 * texture.height)));
        const from = (ty * texture.width + tx) * 4;
        const to = (y * size + x) * 4;
        const light = 0.58 + 0.48 * Math.max(0, -0.35 * nx - 0.3 * ny + 0.88 * Math.sqrt(1 - square));
        data[to] = Math.min(255, texture.data[from] * light);
        data[to + 1] = Math.min(255, texture.data[from + 1] * light);
        data[to + 2] = Math.min(255, texture.data[from + 2] * light);
        data[to + 3] = 255;
      }
    }
    off.putImageData(pixels, 0, 0);
    rasterCache = { key, canvas };
  }
  ctx.drawImage(rasterCache.canvas, cx - radius, cy - radius, radius * 2, radius * 2);
}

export function atmosphere(ctx: CanvasRenderingContext2D, proj: GeoProjection) {
  const r = proj.scale();
  const [x, y] = proj.translate();
  const glow = ctx.createRadialGradient(x, y, r * 0.97, x, y, r * 1.1);
  glow.addColorStop(0, 'rgba(79,147,184,0.20)');
  glow.addColorStop(0.4, 'rgba(79,147,184,0.10)');
  glow.addColorStop(1, 'rgba(79,147,184,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(x - r * 1.1, y - r * 1.1, r * 2.2, r * 2.2);
}

export function spherePath(ctx: CanvasRenderingContext2D, proj: GeoProjection) {
  ctx.beginPath();
  geoPath(proj, ctx)({ type: 'Sphere' });
}
