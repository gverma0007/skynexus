import { useEffect, useState } from 'react';
import { request } from '../lib/api';
import type { HistoricalCaseData, HistoricalChannel, StudyCase } from '../lib/research-types';
import { fmtNum } from '../lib/format';
import Icon from './Icon';
import { Empty, ErrorNote, Skeleton } from './ui';
import { publicHttpUrl } from './ResearchArtifacts';
import CaseEvaluationResults from './CaseEvaluationResults';

export function historicalTime(value: string | undefined): string {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Timestamp unavailable';
  return new Date(value).toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC';
}

export default function HistoricalCasePlayback({ study }: { study: StudyCase }) {
  const [data, setData] = useState<HistoricalCaseData | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [revealLabels, setRevealLabels] = useState(false);
  useEffect(() => {
    let active = true;
    setError('');
    request<HistoricalCaseData>(`/cases/${encodeURIComponent(study.id)}/data`).then((result) => { if (active) setData(result); }).catch((err) => { if (active) setError(err instanceof Error ? err.message : 'Could not load the historical observations.'); });
    return () => { active = false; };
    // Archived cases are immutable snapshots and do not follow live SSE updates.
  }, [study.id, reload]);
  const samples = data?.times.length ?? 0;
  const index = Math.min(frame, Math.max(0, samples - 1));
  const cadence = data?.cadence_hours;
  const stepLabel = cadence && cadence < 1 ? `${fmtNum(cadence * 60)} minutes` : cadence && cadence % 24 === 0 ? `${cadence / 24} ${cadence === 24 ? 'day' : 'days'}` : cadence ? `${cadence} ${cadence === 1 ? 'hour' : 'hours'}` : 'sample';
  useEffect(() => {
    if (!playing || !samples) return;
    const timer = setInterval(() => setFrame((current) => {
      if (current >= samples - 1) { setPlaying(false); return current; }
      return current + 1;
    }), Math.max(100, 2000 / speed));
    return () => clearInterval(timer);
  }, [playing, speed, samples]);
  const step = (amount: number) => { setPlaying(false); setFrame((current) => Math.max(0, Math.min(samples - 1, current + amount))); };
  if (error) return <section className="panel"><ErrorNote message={error} onRetry={() => setReload((current) => current + 1)} /></section>;
  if (!data) return <section className="panel pad"><Skeleton rows={7} /></section>;
  if (!samples || !data.channels.length) return <section className="panel"><Empty title="No replayable observations">The imported case contains no time series. Review its provenance and limitations before evaluating it.</Empty></section>;
  return <div className="historical-case-playback">
    <div className="research-notice"><Icon name="replay" size={18} /><div>This replay uses downloaded historical measurements, independently of the live-source viewer. Source values, time resolution and missing observations are retained. Event labels provide a study reference, not a confirmed explanation.</div></div>
    <div className="historical-label-context"><span className="subtle-badge">{data.label_kind === 'independent_annotations' ? 'Independent annotations' : data.label_kind === 'event_window_proxy' ? 'Event-window proxy labels' : 'Study labels'}</span><p>{data.label_definition}</p>{data.label_kind === 'event_window_proxy' && <p>A documented event interval is an association target, not independently verified operational impact.</p>}{data.limitations.filter((limitation) => limitation.toLowerCase().includes('timezone')).map((limitation) => <p key={limitation}>{limitation}</p>)}</div>
    <div className="panel replay-controls">
      <div className="forecast-target historical-clock"><span>Historical clock</span><b>{historicalTime(data.times[index])}</b><small>Sample {index + 1} of {samples} · {stepLabel} per step</small></div>
      <div className="replay-transport"><button className="btn" disabled={index <= 0} aria-label={`Step back ${stepLabel}`} onClick={() => step(-1)}>−1 step</button><button className="btn" disabled={samples < 2} aria-pressed={playing} onClick={() => { if (!playing && index >= samples - 1) setFrame(0); setPlaying(!playing); }}><Icon name={playing ? 'pause' : 'play'} size={15} />{playing ? 'Pause' : 'Play'}</button><button className="btn" disabled={index >= samples - 1} aria-label={`Step forward ${stepLabel}`} onClick={() => step(1)}>+1 step</button></div>
      <label className="field"><span>Playback speed</span><select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>{[1, 5, 20].map((value) => <option key={value} value={value}>{value}×</option>)}</select></label>
    </div>
    <section className="panel historical-playback"><div className="ph"><h3>Historical measurements</h3><label className="label-reveal"><input type="checkbox" checked={revealLabels} onChange={(event) => setRevealLabels(event.target.checked)} />Reveal event labels</label></div>
      <div className="simulation-scrubber"><label htmlFor="historical-sample">Sample {index + 1} / {samples}</label><input id="historical-sample" type="range" min="0" max={samples - 1} value={index} onChange={(event) => { setPlaying(false); setFrame(Number(event.target.value)); }} /><span>{data.channels.filter((channel) => channel.values[index] != null).length} of {data.channels.length} channels observed</span></div>
      <div className="historical-signal-grid">{data.channels.map((channel) => <HistoricalSignal key={channel.id} channel={channel} frame={index} times={data.times} cadenceHours={data.cadence_hours} labels={revealLabels ? data.labels : undefined} />)}</div>
      <p className="simulation-footnote">{revealLabels ? 'Shading marks the study event labels; these are not model predictions. ' : 'Event labels are hidden. '}{data.label_definition || 'No event-label definition was provided.'} Null values remain gaps; different channels retain their own units.</p>
    </section>
    <CaseEvaluationResults caseId={study.id} saved={data.evaluation} times={data.times} />
    <section className="panel historical-provenance"><div className="ph"><h3>Dataset provenance</h3><span className="subtle-badge">Historical observations</span></div><div className="case-body"><ul>{data.provenance.map((source, i) => {
      const url = publicHttpUrl(source.url ?? source.provenance_url);
      return <li key={`${url ?? source.name}-${i}`}><b>{source.name ?? source.source ?? `Source ${i + 1}`}</b>{url && <a href={url} target="_blank" rel="noreferrer">View source <Icon name="arrow" size={12} /></a>}{source.retrieved_at && <small>Retrieved {historicalTime(source.retrieved_at)}</small>}{source.sha256 && <details><summary>Dataset fingerprint</summary><code>{source.sha256}</code></details>}</li>;
    })}</ul>{!!data.limitations.length && <div className="evaluation-limitations"><h4>Interpretation & limitations</h4><ul>{data.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div>}</div></section>
  </div>;
}

function HistoricalSignal({ channel, frame, times, cadenceHours, labels }: { channel: HistoricalChannel; frame: number; times: string[]; cadenceHours: number; labels?: boolean[] }) {
  const values = channel.values.slice(0, frame + 1);
  const observed = values.filter((value): value is number => value !== null && Number.isFinite(value));
  const lowest = observed.length ? Math.min(...observed) : 0, highest = observed.length ? Math.max(...observed) : 1;
  const spread = Math.max(highest - lowest, Math.abs(highest) * .1, 1e-6);
  const min = lowest - spread * .12, max = highest + spread * .12;
  const start = Date.parse(times[0]), duration = Math.max(1, Date.parse(times.at(-1)!) - start);
  const x = (i: number) => 52 + (Date.parse(times[i]) - start) / duration * 400;
  const y = (value: number) => 145 - (value - min) / (max - min) * 115;
  let connected = false;
  const line = values.map((value, i) => { if (value === null || !Number.isFinite(value)) { connected = false; return ''; } if (i > 0 && cadenceHours > 0 && Date.parse(times[i]) - Date.parse(times[i - 1]) > cadenceHours * 3600_000 * 1.5) connected = false; const segment = `${connected ? 'L' : 'M'}${x(i).toFixed(1)},${y(value).toFixed(1)}`; connected = true; return segment; }).join('');
  const source = publicHttpUrl(channel.provenance_url);
  return <article className="historical-signal"><div className="historical-signal-heading"><div><span>{channel.domain}</span><h4>{channel.label}</h4></div><strong>{channel.values[frame] == null ? 'Unavailable' : fmtNum(channel.values[frame], Math.abs(channel.values[frame]!) < 10 ? 3 : 1)}<small>{channel.unit}</small></strong></div>
    <svg viewBox="0 0 480 182" role="img" aria-label={`${channel.label} in ${channel.unit} through ${historicalTime(times[frame])}. Missing values are gaps.`}>
      {[min, (min + max) / 2, max].map((value) => <g key={value}><line x1="52" x2="452" y1={y(value)} y2={y(value)} stroke="#E9EEE8" /><text x="44" y={y(value) + 3} textAnchor="end" className="axis">{fmtNum(value, Math.abs(value) < 10 ? 2 : 0)}</text></g>)}
      {labels?.slice(0, frame + 1).map((active, i) => active ? <rect key={i} x={x(i)} y="20" width={Math.max(1, i < times.length - 1 ? x(i + 1) - x(i) : 1)} height="125" fill="#EAD6B0" opacity=".45" /> : null)}
      {observed.length ? <path d={line} fill="none" stroke="#315E4D" strokeWidth="1.7" /> : <text x="250" y="82" textAnchor="middle" className="axis">No observations yet</text>}
      <line x1={x(frame)} x2={x(frame)} y1="20" y2="145" stroke="#93AA9B" />
      {channel.values[frame] != null && <circle cx={x(frame)} cy={y(channel.values[frame]!)} r="3" fill="#315E4D" />}
      {[0, Math.floor((times.length - 1) / 2), times.length - 1].map((i, tick) => <text key={`${i}-${tick}`} x={x(i)} y="169" textAnchor={tick === 0 ? 'start' : tick === 2 ? 'end' : 'middle'} className="axis">{new Date(times[i]).toLocaleDateString([], { month: 'short', day: 'numeric', year: '2-digit', timeZone: 'UTC' })}</text>)}
    </svg><div className="historical-channel-footer"><span>{observed.length} observed · {values.length - observed.length} missing through this sample</span>{source && <a href={source} target="_blank" rel="noreferrer">Source <Icon name="arrow" size={12} /></a>}</div>
  </article>;
}
