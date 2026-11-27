import { useState } from 'react';
import type { HistoricalCaseEvaluation } from '../lib/research-types';
import { fmtNum } from '../lib/format';

function utc(value: string): string { return new Date(value).toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'; }

export function HistoricalForecastPlot({ forecast, times }: { forecast: HistoricalCaseEvaluation['forecast']; times: string[] }) {
  const [sample, setSample] = useState(0);
  const points = (forecast.predictions ?? []).filter((point) => point.horizon_hours === forecast.horizon_hours && times[point.target_index] && [point.actual, point.value, point.low, point.high].every(Number.isFinite));
  if (!points.length) return null;
  const selected = points[Math.min(sample, points.length - 1)];
  const values = points.flatMap((point) => [point.actual, point.value, point.low, point.high]);
  const low = Math.min(...values), high = Math.max(...values), pad = Math.max(high - low, Math.abs(high) * .1, 1e-6) * .1;
  const min = low - pad, max = high + pad;
  const start = Date.parse(times[points[0].target_index]), duration = Math.max(1, Date.parse(times[points.at(-1)!.target_index]) - start);
  const x = (index: number) => 60 + (Date.parse(times[index]) - start) / duration * 600;
  const y = (value: number) => 175 - (value - min) / (max - min) * 145;
  return <div className="historical-evaluation-plot"><h5>Held-out forecast samples</h5><p>Each marker is an evaluated origin’s {forecast.horizon_hours}-hour forecast. Bars show the fitted interval; source units are retained.</p><svg viewBox="0 0 700 215" role="img" aria-label={`Observed values compared with ${forecast.horizon_hours}-hour forecasts in ${forecast.unit}`}>
    {[min, (min + max) / 2, max].map((value) => <g key={value}><line x1="60" x2="660" y1={y(value)} y2={y(value)} stroke="#E9EEE8" /><text x="51" y={y(value) + 3} textAnchor="end" className="axis">{fmtNum(value, Math.abs(value) < 10 ? 2 : 0)}</text></g>)}
    {points.map((point) => <g key={`${point.origin_index}-${point.target_index}`}><line x1={x(point.target_index)} x2={x(point.target_index)} y1={y(point.low)} y2={y(point.high)} stroke="#B7CEC0" strokeWidth="3" opacity=".7" /><circle cx={x(point.target_index)} cy={y(point.value)} r="2.6" fill="#527B97" /><circle cx={x(point.target_index)} cy={y(point.actual)} r="2.2" fill="#315E4D" /></g>)}
    <line x1={x(selected.target_index)} x2={x(selected.target_index)} y1="22" y2="175" stroke="#9BAEA4" strokeDasharray="3 3" />
    {[points[0], points.at(-1)!].map((point, i) => <text key={i} x={x(point.target_index)} y="199" textAnchor={i ? 'end' : 'start'} className="axis">{new Date(times[point.target_index]).toLocaleDateString([], { month: 'short', day: 'numeric', year: '2-digit', timeZone: 'UTC' })}</text>)}
  </svg><div className="chart-key"><span><i />Observed</span><span><i className="forecast-key" />Predicted</span><span><i className="interval-key" />Model interval</span></div><label className="evaluation-sample-picker">Inspect evaluated sample<input type="range" min="0" max={points.length - 1} value={Math.min(sample, points.length - 1)} onChange={(event) => setSample(Number(event.target.value))} /></label><div className="evaluation-point-detail"><span>Origin {utc(times[selected.origin_index])}</span><span>Target {utc(times[selected.target_index])}</span><b>Observed {fmtNum(selected.actual, 3)}</b><span>Predicted {fmtNum(selected.value, 3)}</span><span>Interval {fmtNum(selected.low, 3)}–{fmtNum(selected.high, 3)} {forecast.unit}</span></div></div>;
}

export function HistoricalWarningPlot({ warning }: { warning: HistoricalCaseEvaluation['advance_warning'] }) {
  const [sample, setSample] = useState(0);
  const points = (warning.predictions ?? []).filter((point) => Number.isFinite(point.probability) && Number.isFinite(Date.parse(point.time)));
  if (!points.length) return null;
  const start = Date.parse(points[0].time), duration = Math.max(1, Date.parse(points.at(-1)!.time) - start);
  const x = (time: string) => 60 + (Date.parse(time) - start) / duration * 600;
  const y = (value: number) => 175 - Math.max(0, Math.min(1, value)) * 145;
  const selected = points[Math.min(sample, points.length - 1)];
  const path = points.map((point, i) => `${i && point.index === points[i - 1].index + 1 ? 'L' : 'M'}${x(point.time).toFixed(1)},${y(point.probability).toFixed(1)}`).join('');
  return <div className="historical-evaluation-plot"><h5>Held-out warning probabilities</h5><p>Probabilities refer to the annotated onset target over the next {warning.horizon_hours} hours. Reference labels can differ from physical incident onset.</p><svg viewBox="0 0 700 215" role="img" aria-label="Held-out onset warning probabilities, calibration threshold and positive target samples">
    {[0, .5, 1].map((value) => <g key={value}><line x1="60" x2="660" y1={y(value)} y2={y(value)} stroke="#E9EEE8" /><text x="51" y={y(value) + 3} textAnchor="end" className="axis">{value * 100}%</text></g>)}
    {points.map((point, i) => point.outcome ? <rect key={point.time} x={x(point.time)} y="25" width={Math.max(.7, i < points.length - 1 ? (x(points[i + 1].time) - x(point.time)) / Math.max(1, points[i + 1].index - point.index) : .7)} height="150" fill="#EAD6B0" opacity=".5" /> : null)}
    {warning.threshold != null && <line x1="60" x2="660" y1={y(warning.threshold)} y2={y(warning.threshold)} stroke="#A88551" strokeDasharray="4 4" />}
    <path d={path} fill="none" stroke="#527B97" strokeWidth="1.4" /><line x1={x(selected.time)} x2={x(selected.time)} y1="22" y2="175" stroke="#8C9C94" /><circle cx={x(selected.time)} cy={y(selected.probability)} r="3" fill="#315E4D" />
    {[points[0], points.at(-1)!].map((point, i) => <text key={i} x={x(point.time)} y="199" textAnchor={i ? 'end' : 'start'} className="axis">{new Date(point.time).toLocaleDateString([], { month: 'short', day: 'numeric', year: '2-digit', timeZone: 'UTC' })}</text>)}
  </svg><div className="chart-key"><span><i className="forecast-key" />Warning probability</span><span><i style={{ background: '#EAD6B0' }} />Positive target sample</span><span>Dashed line: calibration threshold</span></div><label className="evaluation-sample-picker">Inspect warning sample<input type="range" min="0" max={points.length - 1} value={Math.min(sample, points.length - 1)} onChange={(event) => setSample(Number(event.target.value))} /></label><div className="evaluation-point-detail"><span>{utc(selected.time)}</span><b>{fmtNum(selected.probability * 100, 2)}% predicted</b><span>Reference outcome: {selected.outcome ? 'onset within horizon' : 'no onset within horizon'}</span></div></div>;
}
