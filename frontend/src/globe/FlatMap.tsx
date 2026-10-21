import { useEffect, useRef, useState } from 'react';
import { geoEquirectangular, geoPath } from 'd3-geo';
import { COLORS } from './draw';
import { useAtlas } from './Globe';
import type { GeoPermissibleObjects } from 'd3-geo';

interface TrackPoint {
  lat: number;
  lon: number;
  offset_min?: number;
}

interface Props {
  track?: TrackPoint[];
  current?: { lat: number; lon: number } | null;
  dots?: { lat: number; lon: number; mag: number; id: string }[];
  boxes?: { ring: [number, number][]; strong?: boolean }[];
  highlight?: string | null;
  height?: number;
  caption?: string;
  onDot?: (id: string) => void;
}

/** Equirectangular line map: satellite ground tracks, event locations. */
export default function FlatMap({ track, current, dots, boxes, highlight, height = 220, caption, onDot }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const atlas = useAtlas();
  const [w, setW] = useState(0);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const proj = geoEquirectangular().fitExtent([[2, 2], [Math.max(10, w - 2), height - 2]], { type: 'Sphere' });

  useEffect(() => {
    const c = canvas.current;
    if (!c || !w) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    c.width = w * dpr;
    c.height = height * dpr;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const path = geoPath(proj, ctx);
    ctx.clearRect(0, 0, w, height);
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, w, height);
    if (atlas) {
      ctx.beginPath();
      path(atlas.land as GeoPermissibleObjects);
      ctx.fillStyle = COLORS.land;
      ctx.fill();
      ctx.lineWidth = 0.7;
      ctx.strokeStyle = '#1A1A1A';
      ctx.stroke();
    }
    for (const b of boxes ?? []) {
      ctx.beginPath();
      b.ring.forEach(([lat, lon], i) => {
        const p = proj([lon, lat])!;
        if (i) ctx.lineTo(p[0], p[1]);
        else ctx.moveTo(p[0], p[1]);
      });
      ctx.closePath();
      if (b.strong) {
        ctx.fillStyle = 'rgba(0,0,0,0.06)';
        ctx.fill();
      }
      ctx.setLineDash(b.strong ? [] : [3, 3]);
      ctx.lineWidth = b.strong ? 1.4 : 0.8;
      ctx.strokeStyle = b.strong ? COLORS.ink : COLORS.ink3;
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (track?.length) {
      const segs = (future: boolean) => {
        ctx.beginPath();
        let prev: TrackPoint | null = null;
        for (const t of track) {
          const isFuture = (t.offset_min ?? 0) >= 0;
          if (isFuture !== future) {
            prev = null;
            continue;
          }
          const p = proj([t.lon, t.lat])!;
          if (!prev || Math.abs(t.lon - prev.lon) > 180) ctx.moveTo(p[0], p[1]);
          else ctx.lineTo(p[0], p[1]);
          prev = t;
        }
        ctx.setLineDash(future ? [5, 4] : []);
        ctx.lineWidth = 1.6;
        ctx.strokeStyle = COLORS.ink;
        ctx.stroke();
        ctx.setLineDash([]);
      };
      segs(false);
      segs(true);
    }
    for (const d of dots ?? []) {
      const p = proj([d.lon, d.lat])!;
      const s = Math.max(2.5, 2 + (d.mag - 2.5) * 1.3) * (d.id === highlight ? 1.6 : 1);
      ctx.beginPath();
      ctx.moveTo(p[0], p[1] - s);
      ctx.lineTo(p[0] + s, p[1]);
      ctx.lineTo(p[0], p[1] + s);
      ctx.lineTo(p[0] - s, p[1]);
      ctx.closePath();
      ctx.fillStyle = d.mag >= 5.5 ? COLORS.signal : COLORS.ink;
      ctx.fill();
      if (d.id === highlight) {
        ctx.beginPath();
        ctx.arc(p[0], p[1], s + 5, 0, Math.PI * 2);
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = COLORS.ink;
        ctx.stroke();
      }
    }
    if (current) {
      const p = proj([current.lon, current.lat])!;
      ctx.beginPath();
      ctx.arc(p[0], p[1], 5, 0, Math.PI * 2);
      ctx.fillStyle = COLORS.ink;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(p[0], p[1], 9.5, 0, Math.PI * 2);
      ctx.lineWidth = 1.4;
      ctx.strokeStyle = COLORS.ink;
      ctx.stroke();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atlas, w, height, track, current, dots, boxes, highlight]);

  const onClick = (ev: React.MouseEvent) => {
    if (!onDot || !dots?.length) return;
    const r = canvas.current!.getBoundingClientRect();
    const x = ev.clientX - r.left;
    const y = ev.clientY - r.top;
    let best: string | null = null;
    let bd = 100;
    for (const d of dots) {
      const p = proj([d.lon, d.lat])!;
      const dd = (p[0] - x) ** 2 + (p[1] - y) ** 2;
      if (dd < bd) {
        bd = dd;
        best = d.id;
      }
    }
    if (best) onDot(best);
  };

  return (
    <div ref={wrap} className="flatmap">
      <canvas ref={canvas} style={{ width: w, height }} onClick={onClick} role="img" aria-label={caption ?? 'Map'} />
      {caption && <p className="flatmap-caption">{caption}</p>}
    </div>
  );
}
