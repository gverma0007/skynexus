import { useEffect, useState } from 'react';
import { api, clearApiCache, request } from '../lib/api';
import type { Region } from '../lib/api';
import type { DomainForecast, Evaluation, ExperimentRun, Exposure, NumericSeries, ResearchAsset, StudyCase, SyntheticCaseData } from '../lib/research-types';
import { usePoll } from '../lib/usePoll';
import { useViewer, viewer } from '../lib/viewer';
import { href } from '../lib/router';
import { fmtDateTime, fmtNum } from '../lib/format';
import { Empty, ErrorNote, Skeleton } from '../components/ui';
import Icon from '../components/Icon';
import TrafficChart from '../components/TrafficChart';
import SeriesForecastChart from '../components/SeriesForecastChart';
import ResearchArtifacts, { publicHttpUrl } from '../components/ResearchArtifacts';
import HistoricalCasePlayback, { historicalTime } from '../components/HistoricalCasePlayback';
import { PageHeader } from './Research';

const DOMAINS: Record<string, string> = { aviation: 'Aviation', maritime: 'Maritime', environment: 'Environment', transit: 'Surface transport', infrastructure: 'Infrastructure', space: 'Space', events: 'Event context' };
const seriesId = (series: NumericSeries) => JSON.stringify([series.source, series.entity, series.metric]);
const pct = (value: number | null | undefined) => value == null ? 'Not defined' : `${fmtNum(value * 100, 1)}%`;
function Notice({ children, synthetic = false }: { children: React.ReactNode; synthetic?: boolean }) { return <div className={`research-notice ${synthetic ? 'synthetic-notice' : ''}`}><Icon name={synthetic ? 'experiments' : 'shield'} size={18} /><div>{children}</div></div>; }
function Limitations({ items }: { items?: string[] }) { return items?.length ? <div className="evaluation-limitations"><h4>Interpretation & limitations</h4><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></div> : null; }

export function Forecasts({ regions }: { regions: Region[] | null }) {
  const [tab, setTab] = useState<'domains' | 'aviation'>('domains');
  return <div className="page research-page"><PageHeader title="Forecasts & outlook" description="Define the measurement, inspect its history, and compare predictions with held-out observations." />
    <div className="domain-tabs" role="tablist" aria-label="Forecast type"><button role="tab" aria-selected={tab === 'domains'} className={tab === 'domains' ? 'active' : ''} onClick={() => setTab('domains')}>Domain series</button><button role="tab" aria-selected={tab === 'aviation'} className={tab === 'aviation' ? 'active' : ''} onClick={() => setTab('aviation')}>Regional aviation outlook</button></div>
    {tab === 'domains' ? <DomainForecasts /> : <AviationOutlook regions={regions} />}
  </div>;
}

function DomainForecasts() {
  const context = useViewer();
  const [domain, setDomain] = useState('infrastructure');
  const [selection, setSelection] = useState('');
  const [horizon, setHorizon] = useState(6);
  const series = usePoll(() => request<{ series: NumericSeries[] }>(`/signals/${domain}/analysis`), 60_000, [domain]);
  const selected = series.data?.series.find((item) => seriesId(item) === selection) ?? series.data?.series[0];
  const forecast = usePoll(() => {
    if (!selected || context.dataset === 'demo') return Promise.resolve<DomainForecast | null>(null);
    const params = new URLSearchParams({ source: selected.source, entity: selected.entity, metric: selected.metric, horizon: String(horizon) });
    return request<DomainForecast>(`/signals/${domain}/forecast?${params}`);
  }, 60_000, [domain, selected?.source, selected?.entity, selected?.metric, horizon, context.asOf]);
  const ready = forecast.data?.status === 'ready';
  return <>
    <Notice>A forecast describes a specific numerical measurement. Its model interval is not a probability of a disaster or disruption. Held-out errors measure performance on the recorded series, not general reliability across regions.</Notice>
    <div className="panel forecast-builder"><div className="form-row"><label className="field"><span>Domain</span><select value={domain} onChange={(event) => { setDomain(event.target.value); setSelection(''); }}>{Object.entries(DOMAINS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="field grow"><span>Recorded series</span><select value={selected ? seriesId(selected) : ''} onChange={(event) => setSelection(event.target.value)}><option value="">Select an available measurement</option>{series.data?.series.map((item) => <option key={seriesId(item)} value={seriesId(item)}>{item.source} / {item.entity} / {item.metric}</option>)}</select></label><label className="field"><span>Forecast horizon</span><select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>{[1, 6, 12, 24].map((hours) => <option key={hours} value={hours}>{hours} {hours === 1 ? 'hour' : 'hours'}</option>)}</select></label></div>
      {selected && <div className="forecast-selection-summary"><span><b>{selected.metric.replaceAll('_', ' ')}</b> · {selected.unit || 'Source units'}</span><span>{fmtNum(selected.baseline_days, 1)} days observed</span>{selected.coverage_pct !== undefined && <span>{fmtNum(selected.coverage_pct, 1)}% hourly coverage</span>}</div>}
    </div>
    {series.error && <ErrorNote message={series.error} onRetry={series.refresh} />}
    {forecast.error && <ErrorNote message={forecast.error} onRetry={forecast.refresh} />}
    {context.dataset === 'demo' ? <section className="panel"><Empty title="Synthetic benchmarks are evaluated separately">Generated scenario performance is available in Experiments. Source-based forecasts are never relabelled as real-world predictions.<a className="btn" href={href('experiments')}>Open synthetic benchmark <Icon name="arrow" size={14} /></a></Empty></section> : !series.data && !series.error ? <div className="pad"><Skeleton rows={6} /></div> : !selected ? <section className="panel"><Empty title="A forecast starts with a recorded series">No numerical measurements are available in this domain yet. Inspect the provider’s status or import an attributed historical series.<a className="btn" href={href('sources')}>Inspect sources <Icon name="arrow" size={14} /></a></Empty></section> : forecast.loading && !forecast.data ? <div className="pad"><Skeleton rows={6} /></div> : forecast.data ? <section className="panel forecast-panel"><div className="ph"><h3>{forecast.data.metric.replaceAll('_', ' ')}</h3><span className="subtle-badge">{ready ? 'Source-series forecast' : 'Insufficient history'}</span></div>
      {ready ? <SeriesForecastChart forecast={forecast.data} /> : <Empty title="More complete history is needed">{forecast.data.message ?? 'Forecasting requires at least 96 complete hourly observations. Missing hours are not filled with invented values.'}</Empty>}
      <div className="forecast-method"><Icon name="forecasts" /><div><b>{forecast.data.method || 'No fitted forecast available'}</b><span>{forecast.data.source} / {forecast.data.entity} · {horizon}-hour horizon</span></div></div>
      {forecast.data.evaluation && <EvaluationResults evaluation={forecast.data.evaluation} />}
      <Limitations items={forecast.data.limitations} /><ResearchArtifacts artifacts={forecast.data.artifacts} />
    </section> : null}
  </>;
}

function AviationOutlook({ regions }: { regions: Region[] | null }) {
  const [id, setId] = useState('');
  useEffect(() => { if (!id && regions?.length) setId(regions[0].region_id); }, [id, regions]);
  const history = usePoll(() => id ? api.history(id, 48) : Promise.resolve(null), 60_000, [id]);
  const forecast = usePoll(() => id ? api.forecast(id) : Promise.resolve(null), 60_000, [id]);
  return <><div className="panel form-row"><label className="field"><span>Region</span><select value={id} onChange={(event) => setId(event.target.value)}><option value="">Choose a region</option>{regions?.map((region) => <option key={region.region_id} value={region.region_id}>{region.region_name}</option>)}</select></label><div className="forecast-target"><span>Target</span><b>Observed aircraft per hour</b></div><div className="forecast-target"><span>Horizon</span><b>Next six hours</b></div><span className="subtle-badge">Exploratory projection</span></div><Notice>The regional aviation outlook is a short-term statistical projection. Its band is descriptive, not a calibrated probability interval. It does not predict conflict, airport capacity or route safety.</Notice>
    {forecast.error && <ErrorNote message={forecast.error} onRetry={forecast.refresh} />}<section className="panel forecast-panel"><div className="ph"><h3>{regions?.find((region) => region.region_id === id)?.region_name ?? 'Regional outlook'}</h3><span className="ph-aside">Observed vs projected</span></div>{history.data?.points.length ? <TrafficChart points={history.data.points} forecast={forecast.data} height={270} /> : <Empty title="An outlook needs observation history">Select a region with sufficient complete hourly observations.</Empty>}<div className="forecast-method"><Icon name="forecasts" /><div><b>{forecast.data?.method ?? 'Waiting for observations'}</b><span>Evaluate actual series against persistence and seasonal baselines in Experiments.</span></div></div></section></>;
}

function EvaluationResults({ evaluation }: { evaluation: Partial<Evaluation> }) {
  return <div className="evaluation-results"><div className="evaluation-heading"><h4>Chronological evaluation</h4><span>Errors remain in the measurement’s units</span></div>
    {evaluation.split && <div className="experiment-meta"><span>{evaluation.split.training} training observations</span><span>{evaluation.split.test} held-out observations</span></div>}
    {evaluation.training_observations !== undefined && <div className="experiment-meta"><span>{evaluation.training_observations} training observations</span><span>{evaluation.test_observations} held-out observations</span><span>Rolling forecast origins</span></div>}
    {!!Object.keys(evaluation.forecast_metrics ?? {}).length && <div className="table-wrap"><table><thead><tr><th>Forecast method</th><th>Mean absolute error</th><th>Root mean squared error</th></tr></thead><tbody>{Object.entries(evaluation.forecast_metrics ?? {}).map(([name, metric]) => <tr key={name}><td>{name.replaceAll('_', ' ')}</td><td className="num">{fmtNum(metric.mae, 4)}</td><td className="num">{fmtNum(metric.rmse, 4)}</td></tr>)}</tbody></table></div>}
    {evaluation.interval_observed_coverage != null && <p className="evaluation-coverage">Model interval: <b>{pct(evaluation.interval_observed_coverage)}</b> measured coverage{evaluation.interval_nominal_coverage !== undefined ? ` against ${pct(evaluation.interval_nominal_coverage)} nominal coverage` : ''}. This is not incident confidence.</p>}
    {!!Object.keys(evaluation.by_horizon ?? {}).length && <details className="horizon-details"><summary>Errors by forecast horizon</summary><div className="table-wrap"><table><thead><tr><th>Horizon</th><th>Method</th><th>MAE</th><th>RMSE</th><th>Forecasts tested</th><th>Interval coverage</th></tr></thead><tbody>{Object.entries(evaluation.by_horizon ?? {}).flatMap(([hours, methods]) => Object.entries(methods).map(([name, metric]) => <tr key={`${hours}-${name}`}><td>{hours} h</td><td>{name.replaceAll('_', ' ')}</td><td>{fmtNum(metric.mae, 4)}</td><td>{fmtNum(metric.rmse, 4)}</td><td>{metric.samples ?? '—'}</td><td>{name === 'quantile_gradient_boosting' ? pct(evaluation.interval_coverage_by_horizon?.[hours]) : 'Not applicable'}</td></tr>))}</tbody></table></div></details>}
    {!!Object.keys(evaluation.horizon_metrics ?? {}).length && <div className="table-wrap horizon-table"><table><thead><tr><th>Forecast horizon</th><th>Method</th><th>MAE</th><th>RMSE</th></tr></thead><tbody>{Object.entries(evaluation.horizon_metrics ?? {}).flatMap(([hours, value]) => ('forecast_metrics' in value ? Object.entries(value.forecast_metrics) : [['Forecast', value] as const]).map(([name, metric]) => <tr key={`${hours}-${name}`}><td>{hours} h</td><td>{name.replaceAll('_', ' ')}</td><td>{fmtNum(metric.mae, 4)}</td><td>{fmtNum(metric.rmse, 4)}</td></tr>))}</tbody></table></div>}
  </div>;
}

export function Replay({ regions }: { regions: Region[] | null }) {
  const context = useViewer();
  const catalogue = usePoll(() => request<{ cases: StudyCase[] }>('/cases'), 0);
  const [selectedCase, setSelectedCase] = useState('');
  const [date, setDate] = useState(new Date(Date.now() - 24 * 3600_000).toISOString().slice(0, 16));
  const [region, setRegion] = useState('');
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [frame, setFrame] = useState(119);
  const [revealLabels, setRevealLabels] = useState(false);
  const [downloadingCase, setDownloadingCase] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const study = catalogue.data?.cases.find((item) => item.id === selectedCase);
  const synthetic = study?.dataset_mode === 'synthetic' && study.status === 'available';
  const historicalCase = study?.dataset_mode === 'historical' && study.status === 'available';
  const fixture = usePoll(() => synthetic && study ? request<SyntheticCaseData>(`/cases/${encodeURIComponent(study.id)}/data`) : Promise.resolve<SyntheticCaseData | null>(null), 0, [study?.id, synthetic]);
  const validTime = !!date && Number.isFinite(new Date(`${date}Z`).getTime());
  const history = usePoll(() => region && !synthetic && !historicalCase ? api.history(region, 48) : Promise.resolve(null), 0, [region, context.asOf, synthetic, historicalCase]);
  useEffect(() => { if (!region && regions?.length) setRegion(regions[0].region_id); }, [regions, region]);
  useEffect(() => {
    if (selectedCase) document.getElementById('case-study-detail')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
  }, [selectedCase]);
  const openTime = (value: string) => { setDate(value); clearApiCache(); viewer.setDataset('historical', new Date(`${value}Z`).toISOString()); };
  const step = (hours: number) => { if (synthetic) { setFrame((current) => Math.max(0, Math.min((fixture.data?.traffic.length ?? 240) - 1, current + hours))); return; } if (!validTime) return; const target = Math.min(Date.now(), new Date(`${date}Z`).getTime() + hours * 3600_000); openTime(new Date(target).toISOString().slice(0, 16)); };
  useEffect(() => {
    if (!playing || !validTime || study?.status === 'metadata_only') return;
    if (synthetic) {
      const timer = setInterval(() => setFrame((current) => {
        if (current >= (fixture.data?.traffic.length ?? 240) - 1) { setPlaying(false); return current; }
        return current + 1;
      }), Math.max(100, 2000 / speed));
      return () => clearInterval(timer);
    }
    const timer = setInterval(() => {
      const next = new Date(`${date}Z`).getTime() + 3600_000;
      const stop = study?.event_end ? Math.min(Date.now(), new Date(study.event_end).getTime()) : Date.now();
      if (next > stop) { setPlaying(false); return; }
      openTime(new Date(next).toISOString().slice(0, 16));
    }, Math.max(100, 2000 / speed));
    return () => clearInterval(timer);
    // The callback only advances the explicitly selected analysis clock.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, date, speed, study?.id, study?.status, validTime, synthetic, fixture.data?.traffic.length]);
  return <div className="page research-page"><PageHeader title="Cases & historical replay" description="Inspect the study catalogue, then move through available observations using an explicit clock." action={study ? <button className="btn" onClick={() => { setSelectedCase(''); setPlaying(false); }}>Inspect stored regional history</button> : undefined} />
    <Notice>Download attributed public archives to replay their real measurements. A historical listing alone is not an evaluated result. “Metadata only” means no replayable series is supplied; synthetic cases remain explicitly generated.</Notice>
    {catalogue.error && <ErrorNote message={catalogue.error} onRetry={catalogue.refresh} />}
    <div className="case-catalogue">{catalogue.data?.cases.map((item) => <button key={item.id} className={`panel case-card ${selectedCase === item.id ? 'selected' : ''}`} aria-pressed={selectedCase === item.id} onClick={() => { setSelectedCase(item.id); setPlaying(false); setFrame(119); setRevealLabels(false); setDownloadError(''); if (item.status === 'available' && item.dataset_mode === 'historical') { setDate(new Date(item.event_start).toISOString().slice(0, 16)); const match = regions?.find((row) => row.region_name === item.region); if (match) setRegion(match.region_id); } }}><div className="case-labels"><span className={`subtle-badge ${item.dataset_mode === 'synthetic' ? 'synthetic-badge' : ''}`}>{item.dataset_mode === 'synthetic' ? 'Synthetic' : 'Historical'}</span><span className="case-availability">{item.status === 'available' ? 'Data available' : item.download_supported ? item.status === 'error' ? 'Download needs retry' : 'Public archive available' : 'Metadata only'}</span></div><h3>{item.title}</h3><p>{item.description}</p><small>{item.region} · {item.domains.map((domain) => DOMAINS[domain] ?? domain).join(', ')}</small>{item.samples !== undefined && <small className="block">{fmtNum(item.samples)} native samples</small>}</button>)}</div>
    {study && <section id="case-study-detail" className="panel case-detail"><div className="ph"><h3>{study.title}</h3><span className="subtle-badge">{study.status === 'available' ? 'Available study data' : study.download_supported ? 'Download required' : 'Metadata only — no evaluated series'}</span></div><div className="case-body"><p>{study.description}</p><div className="case-dates"><span>Event start: {historicalTime(study.event_start)}</span><span>Event end: {historicalTime(study.event_end)}</span></div>{publicHttpUrl(study.provenance_url) && <a className="text-link" href={publicHttpUrl(study.provenance_url)!} target="_blank" rel="noreferrer">Study provenance <Icon name="arrow" size={14} /></a>}{study.download_supported && study.status !== 'available' && <div className="case-download"><p>Download the public source archive and verify its checksum before replay. The original cadence and missing values are preserved.</p><button className="btn primary" disabled={!!downloadingCase} onClick={async () => { setDownloadingCase(study.id); setDownloadError(''); try { await request(`/cases/${encodeURIComponent(study.id)}/download`, { method: 'POST' }); catalogue.refresh(); } catch (error) { setDownloadError(error instanceof Error ? error.message : 'Could not download this public archive. Please retry.'); } finally { setDownloadingCase(''); } }}>{downloadingCase === study.id ? 'Downloading public data…' : 'Download public data'}<Icon name="sources" size={15} /></button>{downloadingCase === study.id && <span role="status">Large source archives may take several minutes.</span>}</div>}{downloadError && <ErrorNote message={downloadError} />}<Limitations items={study.limitations} /><ResearchArtifacts artifacts={study.artifacts} /></div></section>}
    {synthetic && <Notice synthetic>This case replays an explicitly generated fixture, independently of the live-source viewer. Simulation hours are ordered samples, not real-world observations.</Notice>}
    {historicalCase && study ? <HistoricalCasePlayback key={study.id} study={study} /> : study?.dataset_mode === 'historical' && study.status !== 'available' ? <section className="panel"><Empty title={study.download_supported ? 'Download this case to begin replay' : 'This catalogue entry contains metadata only'}>{study.download_supported ? 'Select Download public data above. Playback and evaluation become available after the source data is stored and verified.' : 'No imported operational series or evaluation is associated with the selected case.'}</Empty></section> : <>
    <div className="panel replay-controls">{synthetic ? <div className="forecast-target"><span>Simulation clock</span><b>Hour {frame + 1} of {fixture.data?.traffic.length ?? 240}</b></div> : <><label className="field"><span>Analysis time (UTC)</span><input type="datetime-local" value={date} onChange={(event) => { setPlaying(false); setDate(event.target.value); }} /></label><label className="field"><span>Region</span><select value={region} onChange={(event) => setRegion(event.target.value)}>{regions?.map((item) => <option key={item.region_id} value={item.region_id}>{item.region_name}</option>)}</select></label><button className="btn primary" disabled={!validTime || study?.status === 'metadata_only'} onClick={() => openTime(date)}>Open snapshot <Icon name="arrow" size={15} /></button></>}<div className="replay-transport"><button className="btn" disabled={!validTime || study?.status === 'metadata_only' || (synthetic && !fixture.data)} onClick={() => { setPlaying(false); step(-1); }} aria-label="Step back one hour">−1 h</button><button className="btn" disabled={!validTime || study?.status === 'metadata_only' || (synthetic && !fixture.data)} onClick={() => { if (!playing && !synthetic) openTime(date); setPlaying(!playing); }} aria-pressed={playing}><Icon name={playing ? 'pause' : 'play'} size={15} />{playing ? 'Pause' : 'Play'}</button><button className="btn" disabled={!validTime || study?.status === 'metadata_only' || (synthetic && !fixture.data)} onClick={() => { setPlaying(false); step(1); }} aria-label="Step forward one hour">+1 h</button></div><label className="field"><span>Playback speed</span><select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>{[1, 5, 20].map((value) => <option key={value} value={value}>{value}×</option>)}</select></label></div>
    {study?.status === 'metadata_only' && <Notice>This selected case cannot be replayed until its attributed observations are imported. Choose a case with available data, or clear the case to inspect your own stored history.<button className="btn small" onClick={() => setSelectedCase('')}>Inspect other stored history</button></Notice>}
    {synthetic ? <section className="panel synthetic-playback"><div className="ph"><h3>Generated multi-domain signals</h3><label className="label-reveal"><input type="checkbox" checked={revealLabels} onChange={(event) => setRevealLabels(event.target.checked)} />Reveal generated labels</label></div>{fixture.error && <ErrorNote message={fixture.error} onRetry={fixture.refresh} />}{fixture.data ? <><div className="simulation-scrubber"><label htmlFor="simulation-hour">Simulation hour {frame + 1} / {fixture.data.traffic.length}</label><input id="simulation-hour" type="range" min="0" max={fixture.data.traffic.length - 1} value={frame} onChange={(event) => { setPlaying(false); setFrame(Number(event.target.value)); }} /><span>{fixture.data.quality[frame] ? 'Observation available' : 'Missing observation — not zero activity'}</span></div><div className="synthetic-signal-grid">{(['traffic', 'weather', 'transit'] as const).map((field) => <SyntheticSignal key={field} title={field} values={fixture.data![field]} quality={field === 'traffic' ? fixture.data!.quality : undefined} labels={revealLabels ? fixture.data!.labels : undefined} frame={frame} />)}</div><p className="simulation-footnote">First 120 hours: training window. Subsequent 120 hours: evaluation window. {revealLabels ? 'Shading reveals generated disruption labels; labels are not model predictions.' : 'Outcome labels are hidden. Unavailable traffic observations appear as gaps.'}</p></> : !fixture.error ? <div className="pad"><Skeleton rows={6} /></div> : null}</section> : <section className="panel forecast-panel"><div className="ph"><h3>Stored regional observations</h3><span className="subtle-badge">{context.dataset === 'historical' ? 'Historical snapshot' : 'Current viewer dataset'}</span></div>{history.error && <ErrorNote message={history.error} onRetry={history.refresh} />}{study?.status === 'metadata_only' ? <Empty title="This catalogue entry contains metadata only">No imported operational series or evaluation is associated with the selected case.</Empty> : history.data?.points.some((point) => point.aircraft !== null) ? <TrafficChart points={history.data.points} height={250} /> : <Empty title="No stored observations in this window">Select a time covered by retained records. Missing historical data is never generated to fill the chart.</Empty>}</section>}
    </>}
  </div>;
}

function SyntheticSignal({ title, values, quality, labels, frame }: { title: string; values: number[]; quality?: boolean[]; labels?: boolean[]; frame: number }) {
  const available = values.slice(0, frame + 1).filter((_, index) => !quality || quality[index]);
  const min = Math.min(...available), max = Math.max(...available), spread = Math.max(1, max - min);
  const x = (index: number) => 20 + index / Math.max(1, values.length - 1) * 320;
  const y = (value: number) => 105 - (value - min) / spread * 75;
  let open = false;
  const line = values.slice(0, frame + 1).map((value, index) => { if (quality && !quality[index]) { open = false; return ''; } const segment = `${open ? 'L' : 'M'}${x(index)},${y(value)}`; open = true; return segment; }).join('');
  return <article><h4>{title}<span>{quality && !quality[frame] ? 'Unavailable' : fmtNum(values[frame], 1)}</span></h4><svg viewBox="0 0 360 130" role="img" aria-label={`Synthetic ${title} through simulation hour ${frame + 1}; arbitrary generated units`}><line x1="20" x2="340" y1="105" y2="105" stroke="#E8EDE2" />{labels?.slice(0, frame + 1).map((label, index) => label ? <rect key={index} x={x(index)} y="20" width={320 / values.length + .3} height="85" fill="#F1DEC0" opacity=".65" /> : null)}<line x1={x(119)} x2={x(119)} y1="20" y2="105" stroke="#C8D5C1" strokeDasharray="3 3" /><path d={line} stroke="#6A9172" fill="none" strokeWidth="1.6" /><line x1={x(frame)} x2={x(frame)} y1="20" y2="105" stroke="#A7B39E" /><text x="20" y="124" className="axis">Hour 1</text><text x="340" y="124" className="axis" textAnchor="end">Hour {values.length}</text></svg><small>Generated values · Arbitrary fixture units</small></article>;
}

export function Experiments() {
  const results = usePoll(() => request<{ experiments: ExperimentRun[] }>('/experiments'), 0);
  const [domain, setDomain] = useState('infrastructure');
  const series = usePoll(() => request<{ series: NumericSeries[] }>(`/signals/${domain}/analysis`), 0, [domain]);
  const [selection, setSelection] = useState('');
  const [busy, setBusy] = useState<'series' | 'benchmark' | null>(null);
  const [error, setError] = useState('');
  const [fresh, setFresh] = useState<ExperimentRun | null>(null);
  const context = useViewer();
  const runs = fresh && !results.data?.experiments.some((run) => run.id === fresh.id) ? [fresh, ...(results.data?.experiments ?? [])] : results.data?.experiments ?? [];
  const run = async (kind: 'series' | 'benchmark') => {
    const item = series.data?.series.find((candidate) => seriesId(candidate) === selection);
    if (kind === 'series' && !item) return;
    setBusy(kind); setError('');
    try {
      const result = await request<ExperimentRun>(kind === 'benchmark' ? '/experiments/benchmark' : '/experiments', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(kind === 'benchmark' ? {} : { source: item!.source, metric: item!.metric, entity: item!.entity }) });
      setFresh(result); results.refresh();
    } catch (err) { setError(err instanceof Error ? err.message : 'Experiment failed. Please retry.'); } finally { setBusy(null); }
  };
  return <div className="page research-page"><PageHeader title="Experiments & validation" description="Compare detection methods and forecasts using explicit datasets, reproducible runs and honest labels." />
    <Notice>Observed-series forecasts and generated benchmarks answer different questions. Synthetic precision and recall describe controlled scenarios; they do not establish real-world warning accuracy.</Notice>
    <section className="panel benchmark-builder"><div><span className="subtle-badge synthetic-badge">Deterministic synthetic benchmark</span><h2>Test detection across connected domains</h2><p>Run reproducible scenarios with known generated labels. Compare methods, false alerts and detection delay without using external accounts or relabelling synthetic data as historical evidence.</p></div><button className="btn primary" disabled={busy !== null} onClick={() => run('benchmark')}>{busy === 'benchmark' ? 'Running benchmark…' : 'Run synthetic benchmark'}<Icon name="experiments" size={15} /></button></section>
    <section className="panel experiment-builder"><div className="ph"><h3>Evaluate an observed numerical series</h3><span className="subtle-badge">Live observations only</span></div><p className="pad muted m0">Compare persistence, seasonality and quantile gradient boosting on a held-out future window. At least 96 complete hourly observations are required.</p><div className="form-row"><label className="field"><span>Domain</span><select value={domain} onChange={(event) => { setDomain(event.target.value); setSelection(''); }}>{Object.entries(DOMAINS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="field grow"><span>Recorded series</span><select value={selection} onChange={(event) => setSelection(event.target.value)}><option value="">Select a recorded series</option>{series.data?.series.map((item) => <option key={seriesId(item)} value={seriesId(item)}>{item.source} / {item.entity} / {item.metric}</option>)}</select></label><button className="btn" disabled={busy !== null || !selection || context.dataset !== 'live'} onClick={() => run('series')}>{busy === 'series' ? 'Evaluating…' : 'Evaluate series'}<Icon name="forecasts" size={15} /></button></div>{series.data?.series.length === 0 && <p className="pad muted small m0">No numerical series recorded in this domain yet. Inspect Sources for data coverage.</p>}{series.error && <ErrorNote message={series.error} onRetry={series.refresh} />}</section>
    {error && <ErrorNote message={error} />}{results.error && <ErrorNote message={results.error} onRetry={results.refresh} />}
    {runs.length ? runs.map((result) => <ExperimentResult key={result.id} run={result} />) : <section className="panel"><Empty title="No evaluated runs yet">Run the synthetic benchmark to inspect a reproducible generated experiment, or evaluate a sufficiently complete observed series.</Empty></section>}
  </div>;
}

function ExperimentResult({ run }: { run: ExperimentRun }) {
  const synthetic = run.dataset_mode === 'synthetic' || !!run.comparisons;
  return <section className="panel experiment-result"><div className="ph"><h3>{synthetic ? 'Connected-domain synthetic benchmark' : `${run.source} · ${run.metric}`}</h3><span className={`subtle-badge ${synthetic ? 'synthetic-badge' : ''}`}>{synthetic ? 'Synthetic labels only' : 'Observed series'}</span></div>
    <div className="experiment-meta">{run.created_at && <span>{fmtDateTime(run.created_at)}</span>}{run.seed !== undefined && <span>Seed {run.seed}</span>}{run.method_version && <span>{run.method_version}</span>}</div>
    {run.scenarios?.length ? <div className="benchmark-scenarios">{run.scenarios.map((scenario, index) => <article key={scenario.id ?? index}><h4>{scenario.title ?? scenario.name ?? scenario.id?.replaceAll('_', ' ') ?? `Scenario ${index + 1}`}</h4>{scenario.description && <p>{scenario.description}</p>}{scenario.domains?.length ? <small>{scenario.domains.map((domain) => DOMAINS[domain] ?? domain).join(' · ')}</small> : null}<div className="scenario-counts">{scenario.weather_associated_hours !== undefined && <span>{scenario.weather_associated_hours} weather-associated hours</span>}{scenario.missing_hours !== undefined && <span>{scenario.missing_hours} missing hours</span>}</div>{scenario.comparisons?.length ? <details className="scenario-comparisons"><summary>Per-scenario results</summary>{scenario.comparisons.map((comparison) => <div key={comparison.method}><b>{comparison.method.replaceAll('_', ' ')}</b><span>Precision {pct(comparison.precision)} · Recall {pct(comparison.recall)}</span><span>{comparison.false_alerts} false-positive hours · {comparison.detection_delay_hours == null ? 'No detected labelled disruption' : `${comparison.detection_delay_hours} h detection delay`}</span></div>)}</details> : null}</article>)}</div> : null}
    {run.comparisons?.length ? <div className="table-wrap"><table><thead><tr><th>Detection method</th><th>Precision</th><th>Recall</th><th>False-positive hours</th><th>Mean detection delay</th></tr></thead><tbody>{run.comparisons.map((comparison) => <tr key={comparison.method}><td>{comparison.method.replaceAll('_', ' ')}</td><td>{pct(comparison.precision)}</td><td>{pct(comparison.recall)}</td><td>{fmtNum(comparison.false_alerts)}</td><td>{comparison.mean_detection_delay_hours == null ? 'Not detected' : `${fmtNum(comparison.mean_detection_delay_hours, 2)} h`}</td></tr>)}</tbody></table></div> : null}
    {run.forecast_metrics && <EvaluationResults evaluation={run} />}
    <Limitations items={run.limitations} /><ResearchArtifacts artifacts={run.artifacts} />
    <details className="run-reproducibility"><summary>Run reproducibility</summary><p>Run ID: {run.id}</p><p>Dataset: {synthetic ? 'Synthetic generated scenarios' : run.dataset_mode ?? 'Observed source series'}</p><p className="dataset-hash">SHA-256: {run.dataset_hash}</p></details>
  </section>;
}

export function Exposures() {
  const context = useViewer();
  const assets = usePoll(() => request<{ assets: ResearchAsset[] }>('/assets'), 60_000);
  const exposures = usePoll(() => request<{ exposures: Exposure[]; limitations?: string[] }>('/exposures'), 60_000);
  const [selected, setSelected] = useState('');
  const [tab, setTab] = useState<'exposures' | 'assets'>('exposures');
  const chosen = assets.data?.assets.find((asset) => asset.id === selected);
  return <div className="page research-page"><PageHeader title="Infrastructure exposure" description="Inspect attributed assets and their spatial relationships to documented hazards." action={<a className="btn" href={href('signals', 'environment')}>Inspect environment signals <Icon name="arrow" size={14} /></a>} />
    <Notice>An intersection describes geographic exposure. It does not establish damage, service failure or a causal relationship. Observed hazards, forecasts and assumed dependencies must remain distinct.</Notice>
    {context.dataset === 'demo' && <Notice synthetic>Any generated assets or hazards must be labelled synthetic. No live intersection is presented as a synthetic scenario result.</Notice>}
    <div className="domain-tabs" role="tablist" aria-label="Exposure information"><button role="tab" aria-selected={tab === 'exposures'} className={tab === 'exposures' ? 'active' : ''} onClick={() => setTab('exposures')}>Hazard intersections</button><button role="tab" aria-selected={tab === 'assets'} className={tab === 'assets' ? 'active' : ''} onClick={() => setTab('assets')}>Attributed assets</button></div>
    {assets.error && <ErrorNote message={assets.error} onRetry={assets.refresh} />}{exposures.error && <ErrorNote message={exposures.error} onRetry={exposures.refresh} />}
    <section className="panel table-wrap">{tab === 'exposures' ? <><table><thead><tr><th>Exposed asset</th><th>Hazard source</th><th>Relationship</th><th>Evidence type</th><th>Observation time</th><th /></tr></thead><tbody>{exposures.data?.exposures.map((exposure, index) => <tr key={`${exposure.asset_id}-${exposure.hazard_source}-${index}`}><td><button className="table-text-button" onClick={() => setSelected(exposure.asset_id)}>{exposure.name}</button><small className="block muted">{exposure.hazard_kind.replaceAll('_', ' ')}</small></td><td>{exposure.hazard_source}</td><td>{exposure.relation}</td><td><span className="subtle-badge">{exposure.kind ?? 'Observed hazard'}</span></td><td>{fmtDateTime(exposure.observed_at)}</td><td>{publicHttpUrl(exposure.provenance_url) && <a href={publicHttpUrl(exposure.provenance_url)!} target="_blank" rel="noreferrer" aria-label={`Source evidence for ${exposure.name}`}><Icon name="arrow" size={15} /></a>}</td></tr>)}</tbody></table>{exposures.data?.exposures.length === 0 && <Empty title="No attributed hazard intersections available">This can reflect unavailable hazard geometry, incomplete asset coverage or no spatial overlap. It does not establish that the region is unaffected.</Empty>}{!exposures.data && !exposures.error && <div className="pad"><Skeleton rows={5} /></div>}</> : <><table><thead><tr><th>Asset</th><th>Type</th><th>Dataset</th><th>Source</th><th /></tr></thead><tbody>{assets.data?.assets.map((asset) => <tr key={asset.id}><td><button className="table-text-button" onClick={() => setSelected(asset.id)}>{asset.name}</button></td><td>{(asset.asset_type ?? asset.type ?? 'Unspecified').replaceAll('_', ' ')}</td><td>{asset.dataset_mode ?? 'Attributed source data'}</td><td>{publicHttpUrl(asset.provenance_url) ? <a href={publicHttpUrl(asset.provenance_url)!} target="_blank" rel="noreferrer">View provenance</a> : 'Not provided'}</td><td><button className="icon-btn" aria-label={`Inspect ${asset.name}`} onClick={() => setSelected(asset.id)}><Icon name="chevron" size={15} /></button></td></tr>)}</tbody></table>{assets.data?.assets.length === 0 && <Empty title="No assets imported yet">An asset needs an attributed location or geometry before it can support exposure analysis.</Empty>}{!assets.data && !assets.error && <div className="pad"><Skeleton rows={5} /></div>}</>}</section>
    {chosen && <section className="panel observation-inspector"><div className="ph"><h3>{chosen.name}</h3><button className="icon-btn" aria-label="Close asset inspector" onClick={() => setSelected('')}>×</button></div><dl><div><dt>Asset ID</dt><dd>{chosen.id}</dd></div><div><dt>Type</dt><dd>{chosen.asset_type ?? chosen.type}</dd></div><div><dt>Dataset</dt><dd>{chosen.dataset_mode ?? 'Not specified'}</dd></div>{chosen.geometry ? <div><dt>Geometry</dt><dd><code>{JSON.stringify(chosen.geometry)}</code></dd></div> : null}{Object.entries(chosen.properties ?? chosen.properties_json ?? {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? 'Not provided')}</dd></div>)}</dl>{exposures.data?.exposures.filter((exposure) => exposure.asset_id === chosen.id).map((exposure, index) => <Limitations key={index} items={exposure.limitations} />)}</section>}
    <Limitations items={exposures.data?.limitations} />
  </div>;
}
