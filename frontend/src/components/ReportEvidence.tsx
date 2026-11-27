import type { Report } from '../lib/api';
import { fmtDateTime, fmtNum } from '../lib/format';
import { href } from '../lib/router';
import { publicHttpUrl } from './ResearchArtifacts';
import Icon from './Icon';

export default function ReportEvidence({ report }: { report: Report }) {
  const pattern = report.pattern_analysis;
  const evidence = report.source_evidence ?? [];
  const counts: [string, number | undefined][] = [
    ['Complete hours', pattern?.complete_hours], ['Observed hours', pattern?.observed_hours],
    ['Missing hours', pattern?.missing_hours], ['Hours with reference band', pattern?.reference_band_hours],
    ['Below expected band', pattern?.below_band_hours], ['Above expected band', pattern?.above_band_hours],
    ['Longest run outside band', pattern?.longest_run_outside_band_hours],
    ['Weather-coincident outside band', pattern?.weather_coincident_outside_band_hours],
  ];
  return <>
    {pattern && <section id="report-patterns" className="report-research-section"><h3 className="report-section-title">Pattern analysis</h3><p className="report-method-label">{pattern.method.replaceAll('_', ' ')}{pattern.baseline_hours !== undefined ? ` · ${pattern.baseline_hours} baseline hours` : ''}</p>
      <div className="pattern-counts">{counts.filter(([, value]) => value !== undefined).map(([name, value]) => <div key={name}><span>{name}</span><b>{fmtNum(value)}</b></div>)}</div>
      {!!pattern.flagged_hours?.length && <details className="report-flagged"><summary>Inspect {pattern.flagged_hours.length} flagged hours</summary><div className="table-wrap"><table><thead><tr><th>Observed time</th><th>Direction</th><th>Aircraft/h</th><th>Reference band</th><th>Storm index</th></tr></thead><tbody>{pattern.flagged_hours.slice(0, 20).map((hour) => <tr key={hour.time}><td>{fmtDateTime(hour.time)}</td><td>{hour.direction}</td><td>{fmtNum(hour.aircraft, 1)}</td><td>{hour.reference_band ? `${fmtNum(hour.reference_band[0], 1)}–${fmtNum(hour.reference_band[1], 1)}` : 'Unavailable'}</td><td>{hour.storm === null ? 'Unavailable' : fmtNum(hour.storm, 1)}</td></tr>)}</tbody></table></div>{pattern.flagged_hours.length > 20 && <p>Showing the first 20 hours. Export the evidence JSON for all flagged hours.</p>}</details>}
      {pattern.limitations?.length ? <ul className="report-limitations">{pattern.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul> : null}
    </section>}
    {!!report.alternative_explanations?.length && <section id="report-alternatives" className="report-research-section"><h3 className="report-section-title">Alternative explanations</h3><p className="report-section-note">Checks to investigate, not confirmed causes. Several explanations can coexist.</p><div className="report-alternatives">{report.alternative_explanations.map((alternative) => <article key={alternative.explanation}><Icon name="search" size={16} /><div><h4>{alternative.explanation}</h4><p>{alternative.support}</p></div></article>)}</div></section>}
    {report.source_evidence && <section id="report-evidence" className="report-research-section"><h3 className="report-section-title">Source evidence</h3><p className="report-section-note">Observed and received timestamps are separate. Association describes context, not causation.</p>{evidence.length ? <div className="report-evidence-list">{evidence.slice(0, 20).map((item) => {
      const provenance = publicHttpUrl(typeof item.payload.provenance_url === 'string' ? item.payload.provenance_url : typeof item.payload.url === 'string' ? item.payload.url : undefined);
      const summary = summarize(item.payload);
      return <article key={`${item.source}:${item.id}:${item.observed_at}`}><div className="evidence-record-header"><b>{item.source}</b><span className="subtle-badge">{item.kind}</span><span>{item.relation.replaceAll('_', ' ')}</span></div>{summary && <p>{summary}</p>}<dl><div><dt>Observed</dt><dd>{fmtDateTime(item.observed_at)}</dd></div><div><dt>Received</dt><dd>{fmtDateTime(item.received_at)}</dd></div></dl><div className="evidence-record-footer"><span>Record {item.id}</span>{provenance ? <a href={provenance} target="_blank" rel="noreferrer">View provenance <Icon name="arrow" size={12} /></a> : <a href={href('sources', item.source)}>Inspect provider <Icon name="arrow" size={12} /></a>}</div></article>;
    })}</div> : <p className="report-section-note">No attributed source evidence was available for this report’s analysis window. An empty record list does not confirm an absence of disruption.</p>}{evidence.length > 20 && <p className="report-section-note">Showing 20 of {evidence.length} records. The full evidence is retained in the JSON export and archive.</p>}</section>}
    {report.exposures && <section id="report-exposure" className="report-research-section"><h3 className="report-section-title">Infrastructure exposure</h3><p className="report-section-note">Geometric intersection indicates exposure. Damage, closure and operational impact require separate evidence.</p>{report.exposures.length ? <div className="report-exposure-list">{report.exposures.map((exposure, index) => <article key={`${exposure.asset_id}-${index}`}><div className="evidence-record-header"><b>{exposure.name}</b><span className="subtle-badge">{exposure.kind ?? 'Evidence type unspecified'}</span></div><p>{exposure.relation} · {exposure.hazard_kind.replaceAll('_', ' ')} · {exposure.hazard_source}</p><small>{fmtDateTime(exposure.observed_at)}</small>{publicHttpUrl(exposure.provenance_url) && <a href={publicHttpUrl(exposure.provenance_url)!} target="_blank" rel="noreferrer">Source provenance <Icon name="arrow" size={12} /></a>}<ul className="report-limitations">{exposure.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></article>)}</div> : <p className="report-section-note">No attributed asset intersections were available in this window. Coverage and hazard geometry may be incomplete.</p>}</section>}
  </>;
}

function summarize(payload: Record<string, unknown>): string {
  if (typeof payload.metric === 'string' && typeof payload.value === 'number') return `${payload.metric.replaceAll('_', ' ')}: ${fmtNum(payload.value, 3)}${typeof payload.unit === 'string' ? ` ${payload.unit}` : ''}`;
  for (const field of ['title', 'description', 'name', 'event']) if (typeof payload[field] === 'string') return String(payload[field]).slice(0, 320);
  const values = Object.entries(payload).filter(([key, value]) => ['scope', 'entity_id', 'hazard_kind', 'severity', 'status'].includes(key) && ['string', 'number'].includes(typeof value));
  return values.map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' · ');
}
