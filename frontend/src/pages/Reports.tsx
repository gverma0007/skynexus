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
      const r = await api.createReport(rid, h);
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
      </section>
      {error && <ErrorNote message={error} />}

      <div className="rep">
        <section className="panel">
          {busy && !report ? <div className="pad"><Skeleton rows={7} /></div> : report ? (
            <ReportDoc report={report} />
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

function ReportDoc({ report: r }: { report: Report }) {
  const title = `${r.region.name}, last ${r.window_hours} hours`;
  const md = () => [
    `# ${title}`, '',
    `Generated ${r.generated_at ? fmtDateTime(r.generated_at) : 'now'}. Compared with the ${r.window_hours} hours before.`, '',
    '| Measure | Before | After | Change |', '|---|---:|---:|---:|',
    `| Disruption index | ${fmtNum(r.disruption_index.before)} | ${fmtNum(r.disruption_index.after)} | ${r.disruption_index.delta === null ? '–' : r.disruption_index.delta} |`,
    ...[r.aviation_metrics, r.events_metrics, r.weather_metrics, r.satellite_metrics].map(
      (m) => `| ${m.label} (${m.unit}) | ${fmtNum(m.before, 1)} | ${fmtNum(m.after, 1)} | ${fmtPct(m.delta_pct)} |`),
    '', '## Assessment', '', r.overall_assessment, '',
    ...(r.events_metrics.list.length ? ['## Earthquakes in the window', '', ...r.events_metrics.list.map((e) => `- ${e.description} (${fmtDateTime(e.event_date)})`), ''] : []),
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
      {row(r.events_metrics, 0)}
      {row(r.weather_metrics)}
      {row(r.satellite_metrics, 0)}
      <p className="assess">{r.overall_assessment.replace(/\s*Correlation does not establish causation\.\s*$/, '')}</p>
      {r.events_metrics.list.length > 0 && (
        <div className="doc-events">
          <h4>Earthquakes in this window</h4>
          <ul>{r.events_metrics.list.map((e) => <li key={e.event_date + e.magnitude}>{(e.description ?? '').replace(' earthquake — ', ', ')} <span className="muted">({fmtDateTime(e.event_date)})</span></li>)}</ul>
        </div>
      )}
      <div className="disc">
        Correlation does not establish causation. Figures are statistical deviations from public data feeds.
        Data coverage {fmtNum(r.confidence_pct)}%. Written by {r.ai_source === 'claude' ? 'Claude from the computed figures' : 'the built-in template (add an Anthropic API key for AI-written text)'}.
      </div>
    </article>
  );
}
