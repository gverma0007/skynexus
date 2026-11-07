import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import type { MetricDelta, Region, Report } from '../lib/api';
import { fmtDateTime, fmtNum, fmtPct } from '../lib/format';
import { downloadText } from '../lib/download';
import { go } from '../lib/router';
import { usePoll } from '../lib/usePoll';
import { Empty, ErrorNote, Skeleton } from '../components/ui';

interface Props {
  regions: Region[] | null;
  reportId: string | null;
  params: URLSearchParams;
}

const WINDOWS = [6, 24, 72];

export default function Reports({ regions, reportId, params }: Props) {
  const saved = usePoll(api.reports, 0);
  const [region, setRegion] = useState(params.get('region') ?? '');
  const [hours, setHours] = useState(Number(params.get('hours')) || 24);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoRan = useRef(false);

  // load old / historical data of the selected zone from API
  const oldHistory = usePoll(() => (region ? api.history(region, Math.max(hours * 2, 48)) : Promise.resolve(null)), 60_000, [region, hours]);

  // default region: most disrupted
  useEffect(() => {
    if (!region && regions?.length) setRegion(regions[0].region_id);
  }, [regions, region]);

  // open a saved report from the URL
  useEffect(() => {
    if (!reportId) return;
    setError(null);
    api.report(reportId).then(setReport).catch((e: Error) => setError(e.message));
  }, [reportId]);

  const generate = async (rid = region, h = hours) => {
    if (!rid) return;
    setBusy(true);
    setError(null);
    try {
      const [r, hist] = await Promise.all([
        api.createReport(rid, h),
        api.history(rid, Math.max(h * 2, 48)).catch(() => null),
      ]);
      if (hist && !r.historical_data) {
        r.historical_data = hist;
      }
      setReport(r);
      saved.refresh();
      if (r.id) window.history.replaceState(null, '', `#/reports/${r.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not generate the report');
    } finally {
      setBusy(false);
    }
  };

  // deep link: #/reports?region=..&hours=24&run=1
  useEffect(() => {
    if (autoRan.current || params.get('run') !== '1' || !params.get('region')) return;
    autoRan.current = true;
    generate(params.get('region')!, Number(params.get('hours')) || 24);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const remove = async (id: string) => {
    try {
      await api.deleteReport(id);
      if (report?.id === id) {
        setReport(null);
        go('reports');
      }
      saved.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the report');
    }
  };

  return (
    <div className="page">
      <div className="pagehead no-print">
        <div>
          <h1>What changed</h1>
          <p>Compare a region's last hours with the same length of time just before.</p>
        </div>
      </div>
      <section className="panel form-row no-print" aria-label="New report">
        <label className="field">
          <span>Region</span>
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            {(regions ?? []).slice().sort((a, b) => a.region_name.localeCompare(b.region_name)).map((r) => (
              <option key={r.region_id} value={r.region_id}>{r.region_name} ({r.status.toLowerCase()}, {Math.round(r.composite_index)})</option>
            ))}
          </select>
        </label>
        <div className="field">
          <span>Window</span>
          <div className="seg" role="group" aria-label="Window">
            {WINDOWS.map((w) => <button key={w} className={hours === w ? 'on' : ''} aria-pressed={hours === w} onClick={() => setHours(w)}>{w} h</button>)}
          </div>
        </div>
        <button className="btn primary push" onClick={() => generate()} disabled={busy || !region}>
          {busy ? 'Generating…' : 'Generate report'}
        </button>
        {oldHistory.data && (
          <div className="pad small muted" style={{ width: '100%', display: 'flex', gap: 16, flexWrap: 'wrap', borderTop: '1px solid var(--border)', paddingTop: 6, marginTop: 4 }}>
            <span><b>Zone Historical Data (via API):</b> {oldHistory.data.baseline_hours} h baseline ({oldHistory.data.points.length} points)</span>
            <span>Latest: <b>{oldHistory.data.points[oldHistory.data.points.length - 1]?.aircraft ?? '–'}</b> aircraft/h</span>
            {oldHistory.data.points[oldHistory.data.points.length - 1]?.normal_range && (
              <span>Normal band: <b>{Math.round(oldHistory.data.points[oldHistory.data.points.length - 1].normal_range![0])}–{Math.round(oldHistory.data.points[oldHistory.data.points.length - 1].normal_range![1])}</b></span>
            )}
          </div>
        )}
      </section>
      {error && <ErrorNote message={error} />}

      <div className="rep">
        <section className="panel">
          {busy && !report ? <div className="pad"><Skeleton rows={7} /></div> : report ? (
            <ReportDoc report={report} history={report.historical_data ?? oldHistory.data} />
          ) : (
            <Empty title="No report open">Choose a region and a window, then generate a report. Saved reports are listed on the right.</Empty>
          )}
        </section>
        <section className="panel saved no-print" aria-label="Saved reports">
          <div className="ph"><h3>Saved reports</h3><span className="ph-aside">{saved.data?.length ?? 0}</span></div>
          {saved.error && <ErrorNote message={saved.error} onRetry={saved.refresh} />}
          {!saved.data && !saved.error && <div className="pad"><Skeleton rows={4} /></div>}
          {saved.data?.length === 0 && <p className="muted pad m0">Reports you generate are saved here.</p>}
          <ul className="saved-list">
            {saved.data?.map((s) => (
              <li key={s.id} className={report?.id === s.id ? 'sel' : ''}>
                <a href={`#/reports/${s.id}`}>
                  <b>{s.region_name ?? 'Unknown region'}</b>
                  <span className="small muted block">{s.window_hours} h window, {fmtDateTime(s.generated_at)}</span>
                </a>
                <button className="icon-btn" onClick={() => remove(s.id)} aria-label={`Delete report for ${s.region_name}`}>×</button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function row(m: MetricDelta, digits = 1) {
  return (
    <div className="metric" key={m.label}>
      <b>{m.label}</b>
      <span>
        <span className="muted num">{fmtNum(m.before, digits)}</span>&nbsp; to &nbsp;<b className="num">{fmtNum(m.after, digits)}</b>
        <span className="muted small"> {m.unit}</span>
      </span>
      <span className="delta num">{m.before === 0 && (m.after ?? 0) > 0 ? 'new' : fmtPct(m.delta_pct)}</span>
    </div>
  );
}

function ReportDoc({ report: r, history }: { report: Report; history?: { baseline_hours: number; points: any[] } | null }) {
  const title = `${r.region.name}, last ${r.window_hours} hours`;
  const histData = history ?? r.historical_data;
  const md = () => [
    `# ${title}`, '',
    `Generated ${r.generated_at ? fmtDateTime(r.generated_at) : 'now'}. Compared with the ${r.window_hours} hours before.`, '',
    '| Measure | Before | After | Change |', '|---|---:|---:|---:|',
    `| Disruption index | ${fmtNum(r.disruption_index.before)} | ${fmtNum(r.disruption_index.after)} | ${r.disruption_index.delta === null ? '–' : r.disruption_index.delta} |`,
    ...[r.aviation_metrics, r.events_metrics, r.weather_metrics, r.satellite_metrics].map(
      (m) => `| ${m.label} (${m.unit}) | ${fmtNum(m.before, 1)} | ${fmtNum(m.after, 1)} | ${fmtPct(m.delta_pct)} |`),
    ...(r.flight_deviations ? [`| Flight corridor deviations | – | ${r.flight_deviations.deviating_flights} flights (max ${Math.round(r.flight_deviations.max_deviation_km)} km) | ${r.flight_deviations.significant_deviations > 0 ? 'significant' : 'nominal'} |`] : []),
    '', '## Assessment', '', r.overall_assessment, '',
    ...(r.events_metrics.list.length ? ['## Conflict & War Threats in the window', '', ...r.events_metrics.list.map((e) => `- ${(e.description ?? '').replace(' earthquake — ', ', ').replace(/earthquake/gi, 'incident')} (${fmtDateTime(e.event_date)})`), ''] : []),
    ...(histData?.points?.length ? ['## Historical Baseline (API retrieved)', '', `Baseline of ${histData.baseline_hours} hours across preceding period.`, ''] : []),
    `_Data coverage ${fmtNum(r.confidence_pct)}%. Assessment written by ${r.ai_source === 'claude' ? 'Claude' : 'the built-in template'}._`,
  ].join('\n');

  return (
    <article className="doc">
      <header className="doc-head">
        <div>
          <h2>{title}</h2>
          <p className="muted m0">
            {r.generated_at ? `Generated ${fmtDateTime(r.generated_at)}. ` : ''}Compared with the {r.window_hours} hours before.
          </p>
        </div>
        <div className="row-gap no-print">
          <button className="btn" onClick={() => downloadText(`skynexus-${r.region.name.toLowerCase().replace(/\s+/g, '-')}-${r.window_hours}h.md`, md(), 'text/markdown')}>Download Markdown</button>
          <button className="btn" onClick={() => window.print()}>Print or save as PDF</button>
        </div>
      </header>
      <div className="metric index-row">
        <b>Disruption index</b>
        <span><span className="muted num">{fmtNum(r.disruption_index.before)}</span>&nbsp; to &nbsp;<b className="num">{fmtNum(r.disruption_index.after)}</b><span className="muted small"> of 100</span></span>
        <span className="delta num">{r.disruption_index.delta === null ? '–' : `${r.disruption_index.delta > 0 ? '+' : ''}${Math.round(r.disruption_index.delta)}`}</span>
      </div>
      {row(r.aviation_metrics)}
      {r.flight_deviations && (
        <div className="metric">
          <b>Flight corridor deviations</b>
          <span>
            <span className="muted num">{r.flight_deviations.deviating_flights} deviating</span>&nbsp; (max &nbsp;<b className="num">{Math.round(r.flight_deviations.max_deviation_km)} km</b><span className="muted small"> off route</span>)
          </span>
          <span className="delta num" style={{ color: r.flight_deviations.significant_deviations > 0 ? 'var(--crit, #d32f2f)' : 'inherit' }}>
            {r.flight_deviations.significant_deviations > 0 ? `${r.flight_deviations.significant_deviations} significant` : 'nominal'}
          </span>
        </div>
      )}
      {row(r.events_metrics, 0)}
      {row(r.weather_metrics)}
      {row(r.satellite_metrics, 0)}
      <p className="assess">{r.overall_assessment.replace(/\s*Correlation does not establish causation\.\s*$/, '')}</p>
      {histData && histData.points?.length > 0 && (
        <div className="doc-events">
          <h4>Old / Historical Zone Data (retrieved via API)</h4>
          <p className="muted small m0" style={{ marginBottom: 8 }}>
            Baseline of {histData.baseline_hours} hours. Past observations across the comparison window:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
            {histData.points.slice(-6).map((pt: any) => (
              <div key={pt.time} style={{ border: '1px solid var(--border)', borderRadius: 4, padding: '6px 8px', fontSize: '0.8rem' }}>
                <div className="muted">{fmtDateTime(pt.time)}</div>
                <div><b>{pt.aircraft ?? '–'}</b> aircraft/h</div>
                <div className="muted small">Normal: {pt.normal_range ? `${Math.round(pt.normal_range[0])}–${Math.round(pt.normal_range[1])}` : 'calibrating'}</div>
                {pt.storm !== null && <div className="muted small">Storm: {Math.round(pt.storm)}/100</div>}
              </div>
            ))}
          </div>
        </div>
      )}
      {r.events_metrics.list.length > 0 && (
        <div className="doc-events">
          <h4>Conflict & Security Incidents in this window</h4>
          <ul>{r.events_metrics.list.map((e) => <li key={e.event_date + e.magnitude}>{(e.description ?? '').replace(' earthquake — ', ', ').replace(/^M[\d.]+ earthquake — /, 'Incident: ')} <span className="muted">({fmtDateTime(e.event_date)})</span></li>)}</ul>
        </div>
      )}
      <div className="disc">
        Correlation does not establish causation. Figures are statistical deviations from public data feeds.
        Data coverage {fmtNum(r.confidence_pct)}%. Written by {r.ai_source === 'claude' ? 'Claude from the computed figures' : 'the built-in template (add an Anthropic API key for AI-written text)'}.
      </div>
    </article>
  );
}
