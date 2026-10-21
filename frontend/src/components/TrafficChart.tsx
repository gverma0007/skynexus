import { useEffect, useRef, useState } from 'react';
import type { Forecast, HistoryPoint } from '../lib/api';
import { fmtNum, fmtTime } from '../lib/format';

interface Props {
  points: HistoryPoint[];
  forecast?: Forecast | null;
  height?: number;
}

/** Aircraft per hour with the usual range for that hour (grey band) and a
 *  dashed short-term projection. */
export default function TrafficChart({ points, forecast, height = 150 }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(320);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const fc = (forecast?.points ?? []).slice(1);
  const n = points.length + fc.length;
  if (points.length < 2) {
    return <div ref={wrap} className="chart-empty">Not enough hourly data yet. The chart fills in as data arrives.</div>;
  }

  const padL = 30, padR = 8, padT = 8, padB = 20;
  const iw = w - padL - padR;
  const ih = height - padT - padB;
  const vals: number[] = [];
  points.forEach((p) => {
    if (p.aircraft !== null) vals.push(p.aircraft);
    if (p.normal_range) vals.push(p.normal_range[1]);
  });
  fc.forEach((p) => vals.push(p.high));
  const max = Math.max(5, ...vals) * 1.08;
  const x = (i: number) => padL + (i / Math.max(1, n - 1)) * iw;
  const y = (v: number) => padT + ih - (v / max) * ih;

  // normal band
  let band = '';
  const bandPts = points.map((p, i) => (p.normal_range ? [i, p.normal_range] as const : null));
  let open: [number, readonly [number, number]][] = [];
  const flush = () => {
    if (open.length > 1) {
      band += `M${open.map(([i, r]) => `${x(i)},${y(r[1])}`).join('L')}L${[...open].reverse().map(([i, r]) => `${x(i)},${y(r[0])}`).join('L')}Z`;
    }
    open = [];
  };
  bandPts.forEach((b) => (b ? open.push([b[0], b[1]]) : flush()));
  flush();

  // observed line (complete hours), gaps break the line
  let line = '';
  let pen = false;
  points.forEach((p, i) => {
    if (p.aircraft === null || p.partial) {
      pen = false;
      return;
    }
    line += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.aircraft).toFixed(1)}`;
    pen = true;
  });
  const lastComplete = [...points].map((p, i) => [p, i] as const).filter(([p]) => !p.partial && p.aircraft !== null).pop();

  // forecast
  const fStart = points.length - 1;
  const fPath = lastComplete && fc.length
    ? `M${x(lastComplete[1])},${y(lastComplete[0].aircraft!)}` + fc.map((p, k) => `L${x(fStart + 1 + k)},${y(p.value)}`).join('')
    : '';
  const fBand = fc.length
    ? `M${fc.map((p, k) => `${x(fStart + 1 + k)},${y(p.high)}`).join('L')}L${[...fc].reverse().map((p, k) => `${x(fStart + fc.length - k)},${y(p.low)}`).join('L')}Z`
    : '';

  const ticks = [0, Math.round(max / 2), Math.round(max)];
  const labelIdx = [0, Math.floor(points.length / 2), points.length - 1];

  const onMove = (ev: React.MouseEvent<SVGSVGElement>) => {
    const r = ev.currentTarget.getBoundingClientRect();
    const i = Math.round(((ev.clientX - r.left - padL) / iw) * (n - 1));
    setHover(i >= 0 && i < n ? i : null);
  };

  let readout: string | null = null;
  if (hover !== null) {
    if (hover < points.length) {
      const p = points[hover];
      readout = `${fmtTime(p.time)}  ${p.aircraft === null ? 'no data' : `${fmtNum(p.aircraft)} aircraft${p.partial ? ' so far' : ''}`}` +
        (p.normal_range ? `, usual ${fmtNum(p.normal_range[0])}–${fmtNum(p.normal_range[1])}` : '');
    } else {
      const p = fc[hover - points.length];
      readout = `${fmtTime(p.time)}  projected ${fmtNum(p.value)} (${fmtNum(p.low)}–${fmtNum(p.high)})`;
    }
  }

  return (
    <div ref={wrap} className="chart">
      <svg width={w} height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img"
        aria-label="Aircraft per hour with usual range and projection">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={w - padR} y1={y(t)} y2={y(t)} stroke="#EFEFEC" />
            <text x={padL - 6} y={y(t) + 3} textAnchor="end" className="axis">{t}</text>
          </g>
        ))}
        <path d={band} fill="#ECECE9" />
        <path d={fBand} fill="#F3F3F1" />
        <path d={line} fill="none" stroke="#000" strokeWidth={1.6} strokeLinejoin="round" />
        {fPath && <path d={fPath} fill="none" stroke="#000" strokeWidth={1.4} strokeDasharray="4 4" />}
        {lastComplete && <circle cx={x(lastComplete[1])} cy={y(lastComplete[0].aircraft!)} r={3} fill="#000" />}
        {labelIdx.map((i) => (
          <text key={i} x={x(i)} y={height - 4} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'middle' : 'middle'} className="axis">
            {i === points.length - 1 ? 'now' : `${points.length - 1 - i} h ago`}
          </text>
        ))}
        {fc.length > 0 && x(n - 1) - x(points.length - 1) > 44 && <text x={w - padR} y={height - 4} textAnchor="end" className="axis">+{fc.length} h</text>}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={padT} y2={padT + ih} stroke="#000" strokeOpacity={0.35} />}
      </svg>
      <div className="chart-readout" aria-live="polite">{readout ?? 'Hover the chart to read values. Grey band: usual range for that hour.'}</div>
    </div>
  );
}
