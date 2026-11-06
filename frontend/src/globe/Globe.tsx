import { useEffect, useMemo, useRef, useState } from 'react';
import type { GeoProjection } from 'd3-geo';
import type { Topology } from 'topojson-specification';
import { draw, nearest, prepareAtlas, regionAt } from './draw';
import type { Atlas, GlobeEvent, GlobeFlight, GlobeRegion, GlobeSat, Layers } from './draw';

let atlasPromise: Promise<Atlas> | null = null;
export function loadAtlas(): Promise<Atlas> {
  atlasPromise ??= fetch('/world-atlas.json')
    .then((r) => r.json())
    .then((t: Topology) => prepareAtlas(t));
  return atlasPromise;
}

export function useAtlas(): Atlas | null {
  const [atlas, setAtlas] = useState<Atlas | null>(null);
  useEffect(() => {
    let alive = true;
    loadAtlas().then((a) => alive && setAtlas(a)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return atlas;
}

interface Props {
  regions: GlobeRegion[];
  flights: GlobeFlight[];
  sats: GlobeSat[];
  events: GlobeEvent[];
  layers: Layers;
  selectedRegion: string | null;
  selectedSat: number | null;
  focus: { lat: number; lon: number; key: string } | null;
  onSelectRegion: (id: string | null) => void;
  onSelectSat: (id: number) => void;
  onSelectFlight?: (icao24: string) => void;
}

interface Tip {
  x: number;
  y: number;
  title: string;
  sub?: string;
}

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export default function Globe(props: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const projRef = useRef<GeoProjection | null>(null);
  const atlas = useAtlas();
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [rotate, setRotate] = useState<[number, number]>([-60, -22]);
  const [zoom, setZoom] = useState(1);
  const [hoverRegion, setHoverRegion] = useState<string | null>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  const drag = useRef<{ x: number; y: number; r: [number, number]; moved: boolean } | null>(null);
  const anim = useRef<number | null>(null);
  const rotateRef = useRef(rotate);
  rotateRef.current = rotate;

  // size
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setSize({ w: Math.floor(entry.contentRect.width), h: Math.floor(entry.contentRect.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // fly to focus
  const focusKey = props.focus?.key;
  useEffect(() => {
    if (!props.focus) return;
    const target: [number, number] = [-props.focus.lon, Math.max(-60, Math.min(60, -props.focus.lat))];
    if (anim.current) cancelAnimationFrame(anim.current);
    if (reducedMotion()) {
      setRotate(target);
      return;
    }
    const start = performance.now();
    const from = rotateRef.current;
    let dl = target[0] - from[0];
    dl = ((dl + 540) % 360) - 180;
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / 700);
      const e = 1 - Math.pow(1 - k, 3);
      setRotate([from[0] + dl * e, from[1] + (target[1] - from[1]) * e]);
      if (k < 1) anim.current = requestAnimationFrame(step);
    };
    anim.current = requestAnimationFrame(step);
    return () => {
      if (anim.current) cancelAnimationFrame(anim.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey]);

  // render
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || !size.w || !size.h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (c.width !== size.w * dpr || c.height !== size.h * dpr) {
      c.width = size.w * dpr;
      c.height = size.h * dpr;
    }
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    projRef.current = draw(ctx, size.w, size.h, {
      atlas, rotate, zoom, regions: props.regions, flights: props.flights, sats: props.sats,
      events: props.events, layers: props.layers, selectedRegion: props.selectedRegion,
      selectedSat: props.selectedSat, hoverRegion,
    });
  }, [atlas, rotate, zoom, size, props.regions, props.flights, props.sats, props.events, props.layers,
    props.selectedRegion, props.selectedSat, hoverRegion]);

  const pick = (x: number, y: number) => {
    const proj = projRef.current;
    if (!proj) return null;
    const { layers } = props;
    if (layers.satellites) {
      const s = nearest(proj, rotate, props.sats, x, y, 7);
      if (s) return { kind: 'sat' as const, item: s };
    }
    if (layers.events) {
      const e = nearest(proj, rotate, props.events, x, y, 7);
      if (e) return { kind: 'event' as const, item: e };
    }
    if (layers.aircraft) {
      const f = nearest(proj, rotate, props.flights, x, y, 5);
      if (f) return { kind: 'flight' as const, item: f };
    }
    const r = regionAt(proj, props.regions, x, y);
    if (r) return { kind: 'region' as const, item: r };
    return null;
  };

  const local = (ev: React.PointerEvent | React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return [ev.clientX - rect.left, ev.clientY - rect.top] as const;
  };

  const onPointerDown = (ev: React.PointerEvent) => {
    (ev.target as Element).setPointerCapture(ev.pointerId);
    drag.current = { x: ev.clientX, y: ev.clientY, r: rotate, moved: false };
    if (anim.current) cancelAnimationFrame(anim.current);
  };

  const onPointerMove = (ev: React.PointerEvent) => {
    const d = drag.current;
    if (d) {
      const dx = ev.clientX - d.x;
      const dy = ev.clientY - d.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
      const k = 0.35 / zoom;
      setRotate([d.r[0] + dx * k, Math.max(-85, Math.min(85, d.r[1] - dy * k))]);
      setTip(null);
      return;
    }
    const [x, y] = local(ev);
    const hit = pick(x, y);
    setHoverRegion(hit?.kind === 'region' ? hit.item.id : null);
    if (!hit) return setTip(null);
    if (hit.kind === 'sat') setTip({ x, y, title: hit.item.label, sub: 'Satellite. Click for orbit details.' });
    else if (hit.kind === 'event') setTip({ x, y, title: hit.item.label });
    else if (hit.kind === 'flight') setTip({ x, y, title: hit.item.label, sub: 'Aircraft route. Click for planned vs actual path.' });
    else setTip({ x, y, title: `${hit.item.name}`, sub: `Disruption index ${Math.round(hit.item.score)}` });
  };

  const onPointerUp = (ev: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (d?.moved) return;
    const [x, y] = local(ev);
    const hit = pick(x, y);
    if (hit?.kind === 'sat') props.onSelectSat(hit.item.id);
    else if (hit?.kind === 'region') props.onSelectRegion(hit.item.id);
    else if (hit?.kind === 'flight') props.onSelectFlight?.(String(hit.item.id));
  };

  const onWheel = (ev: React.WheelEvent) => {
    setZoom((z) => Math.max(0.8, Math.min(4, z * (ev.deltaY > 0 ? 0.92 : 1.08))));
  };

  // stop page scroll while zooming the globe
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const block = (e: WheelEvent) => e.preventDefault();
    c.addEventListener('wheel', block, { passive: false });
    return () => c.removeEventListener('wheel', block);
  }, []);

  const onKey = (ev: React.KeyboardEvent) => {
    const step = 10 / zoom;
    if (ev.key === 'ArrowLeft') setRotate(([l, p]) => [l + step, p]);
    else if (ev.key === 'ArrowRight') setRotate(([l, p]) => [l - step, p]);
    else if (ev.key === 'ArrowUp') setRotate(([l, p]) => [l, Math.max(-85, p - step)]);
    else if (ev.key === 'ArrowDown') setRotate(([l, p]) => [l, Math.min(85, p + step)]);
    else if (ev.key === '+' || ev.key === '=') setZoom((z) => Math.min(4, z * 1.2));
    else if (ev.key === '-') setZoom((z) => Math.max(0.8, z / 1.2));
    else return;
    ev.preventDefault();
  };

  const cursor = useMemo(() => (hoverRegion || tip ? 'pointer' : 'grab'), [hoverRegion, tip]);

  return (
    <div ref={wrapRef} className="globe">
      <canvas
        ref={canvasRef}
        style={{ width: size.w, height: size.h, cursor }}
        tabIndex={0}
        aria-label="Globe. Drag or use arrow keys to rotate, plus and minus to zoom."
        role="img"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => {
          setTip(null);
          setHoverRegion(null);
        }}
        onWheel={onWheel}
        onKeyDown={onKey}
      />
      {tip && (
        <div className="tip" style={{ left: tip.x + 14, top: tip.y + 12 }}>
          <b>{tip.title}</b>
          {tip.sub && <span>{tip.sub}</span>}
        </div>
      )}
      <div className="zoom" role="group" aria-label="Zoom">
        <button onClick={() => setZoom((z) => Math.min(4, z * 1.25))} aria-label="Zoom in">+</button>
        <button onClick={() => setZoom((z) => Math.max(0.8, z / 1.25))} aria-label="Zoom out">−</button>
        <button onClick={() => { setZoom(1); setRotate([-60, -22]); }} aria-label="Reset view" className="small">⟲</button>
      </div>
    </div>
  );
}
