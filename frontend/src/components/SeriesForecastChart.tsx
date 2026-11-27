import { useEffect, useRef, useState } from 'react';
import type { DomainForecast } from '../lib/research-types';
import { fmtDateTime, fmtNum } from '../lib/format';

export default function SeriesForecastChart({ forecast }: { forecast: DomainForecast }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(680);
  useEffect(() => { if (!wrap.current) return; const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width))); observer.observe(wrap.current); return () => observer.disconnect(); }, []);
  const history = (forecast.history ?? []).slice(-48).filter((point) => Number.isFinite(point.value));
  const future = (forecast.points ?? []).filter((point) => Number.isFinite(point.value));
  const all = [...history, ...future];
  if (all.length < 2) return <div className="chart-empty">More observations are required to draw this series.</div>;
  const height = 275, left = 53, right = 20, top = 24, bottom = 43;
  const start = new Date(all[0].time).getTime(), end = new Date(all[all.length - 1].time).getTime();
  const values = [...history.map((point) => point.value), ...future.flatMap((point) => [point.low, point.high, point.value])].filter(Number.isFinite);
  const lowest = Math.min(...values), highest = Math.max(...values);
  const spread = Math.max(highest - lowest, Math.abs(highest) * .1, 1e-6);
  const min = lowest - spread * .12, max = highest + spread * .12;
  const x = (time: string) => left + (new Date(time).getTime() - start) / Math.max(1, end - start) * (width - left - right);
  const y = (value: number) => top + (max - value) / (max - min) * (height - top - bottom);
  const path = (points: { time: string; value: number }[]) => points.map((point, i) => `${i ? 'L' : 'M'}${x(point.time).toFixed(1)},${y(point.value).toFixed(1)}`).join('');
  const boundary = history.at(-1);
  const futureLine = boundary && future.length ? [boundary, ...future] : future;
  const band = future.length > 1 ? `${path(future.map((point) => ({ time: point.time, value: point.high })))}${[...future].reverse().map((point) => `L${x(point.time)},${y(point.low)}`).join('')}Z` : '';
  const ticks = [0, .25, .5, .75, 1];
  return <div ref={wrap} className="series-forecast-chart"><svg width={width} height={height} role="img" aria-label={`${forecast.metric.replaceAll('_', ' ')} in ${forecast.unit || 'source units'}: observed history, future forecast and model interval`}>
    {[min, (min + max) / 2, max].map((value) => <g key={value}><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} stroke="#E9EEE8" /><text x={left - 8} y={y(value) + 3} textAnchor="end" className="axis">{fmtNum(value, Math.abs(value) < 10 ? 2 : 0)}</text></g>)}
    {band && <path d={band} fill="#DDEBE5" opacity=".8" />}
    {boundary && future.length > 0 && <line x1={x(boundary.time)} x2={x(boundary.time)} y1={top} y2={height - bottom} stroke="#AABEB2" strokeDasharray="3 4" />}
    <path d={path(history)} fill="none" stroke="#315E4D" strokeWidth="1.7" />
    <path d={path(futureLine)} fill="none" stroke="#527B97" strokeWidth="1.7" strokeDasharray="5 4" />
    {ticks.map((fraction) => { const time = new Date(start + fraction * (end - start)).toISOString(); return <text key={fraction} x={left + fraction * (width - left - right)} y={height - 17} textAnchor={fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle'} className="axis">{new Date(time).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit' })}</text>; })}
  </svg><div className="chart-key"><span><i />Observed</span><span><i className="forecast-key" />Forecast</span><span><i className="interval-key" />Model interval</span><span>{forecast.unit || 'Source units'}</span></div>
    {!!future.length && <details className="forecast-values"><summary>View forecast values</summary><div className="table-wrap"><table><thead><tr><th>Forecast time</th><th>Estimate</th><th>Lower</th><th>Upper</th></tr></thead><tbody>{future.map((point) => <tr key={point.time}><td>{fmtDateTime(point.time)}</td><td>{fmtNum(point.value, 3)}</td><td>{fmtNum(point.low, 3)}</td><td>{fmtNum(point.high, 3)}</td></tr>)}</tbody></table></div></details>}
  </div>;
}
