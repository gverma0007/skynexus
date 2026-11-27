import { useState } from 'react';
import { request } from '../lib/api';
import type { HistoricalCaseEvaluation } from '../lib/research-types';
import { fmtNum } from '../lib/format';
import { ErrorNote } from './ui';
import Icon from './Icon';
import ResearchArtifacts from './ResearchArtifacts';
import { HistoricalForecastPlot, HistoricalWarningPlot } from './HistoricalEvaluationPlots';

const percentage = (value: number | null | undefined) => value == null ? 'Unavailable' : `${fmtNum(value * 100, 1)}%`;
const hours = (value: number | null | undefined) => value == null ? 'Unavailable' : `${fmtNum(value, 1)} h`;
const readable = (value: string | undefined) => value?.replaceAll('_', ' ') ?? 'Unavailable';

export default function CaseEvaluationResults({ caseId, saved, times }: { caseId: string; saved?: HistoricalCaseEvaluation | null; times: string[] }) {
  const [fresh, setFresh] = useState<HistoricalCaseEvaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const result = fresh ?? saved;
  const warning = result?.advance_warning;
  return <section className="panel case-evaluation"><div className="ph"><div><h3>Historical case evaluation</h3><p>Measure held-out performance on this case’s observations.</p></div><button className="btn primary" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { setFresh(await request<HistoricalCaseEvaluation>(`/cases/${encodeURIComponent(caseId)}/evaluate`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' })); } catch (err) { setError(err instanceof Error ? err.message : 'Could not evaluate this case. Please retry.'); } finally { setBusy(false); } }}>{busy ? 'Evaluating case…' : result ? 'Re-evaluate case' : 'Evaluate historical case'}<Icon name="experiments" size={15} /></button></div>
    {error && <ErrorNote message={error} />}
    {!result ? <div className="case-evaluation-intro"><p>Train on earlier samples, calibrate on a separate interval, then evaluate on later observations. Detection labels, numerical forecasts and advance-warning skill are assessed separately.</p><p>One documented event or a short record may be insufficient to fit a warning model. Unavailable metrics remain unavailable.</p></div> : <>
      <div className="case-evaluation-summary"><span className="subtle-badge">Historical observations</span><span>{result.training_observations} training samples</span><span>{result.calibration_observations} calibration samples</span><span>{result.test_observations} held-out samples</span>{result.split_time && <span>Test starts {new Date(result.split_time).toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', timeZone: 'UTC' })} UTC</span>}</div>
      <div className="case-evaluation-block"><div className="evaluation-heading"><h4>Detection against study labels</h4><span>{readable(result.detection.status)}</span></div><p className="case-evaluation-note">{result.detection.label_definition}</p><p className="case-evaluation-note">Label type: {readable(result.detection.label_kind)}. Alert counts are samples at the dataset’s native cadence.</p>
        {result.detection.comparisons.length ? <div className="table-wrap"><table><thead><tr><th>Method</th><th>Precision</th><th>Recall</th><th>F1</th><th>False alert samples</th><th>Mean detection delay</th><th>Event recall</th><th>Test samples</th></tr></thead><tbody>{result.detection.comparisons.map((row) => <tr key={row.method}><td>{readable(row.method)}</td><td>{percentage(row.precision)}</td><td>{percentage(row.recall)}</td><td>{percentage(row.f1)}</td><td>{fmtNum(row.false_alerts)}</td><td>{hours(row.mean_detection_delay_hours)}</td><td>{percentage(row.event_recall)}</td><td>{fmtNum(row.samples)}</td></tr>)}</tbody></table></div> : <p className="case-evaluation-note">No detection comparison is available for this label set.</p>}
      </div>
      <div className="case-evaluation-block"><div className="evaluation-heading"><h4>Numerical forecast performance</h4><span>Errors in {result.forecast.unit || 'source units'}</span></div><p className="case-evaluation-note">Target: {readable(result.forecast.target)}{result.forecast.horizon_hours != null ? ` · ${result.forecast.horizon_hours}-hour horizon` : ''}. Numerical accuracy is separate from event prediction.</p>{result.forecast.message && <p className="case-evaluation-note">{result.forecast.message}</p>}
        {Object.keys(result.forecast.forecast_metrics).length ? <div className="table-wrap"><table><thead><tr><th>Method</th><th>Mean absolute error</th><th>Root mean squared error</th><th>Samples</th></tr></thead><tbody>{Object.entries(result.forecast.forecast_metrics).map(([method, metric]) => <tr key={method}><td>{readable(method)}</td><td>{fmtNum(metric.mae, 4)}</td><td>{fmtNum(metric.rmse, 4)}</td><td>{fmtNum(metric.samples)}</td></tr>)}</tbody></table></div> : <p className="case-evaluation-note">No numerical forecast evaluation is available.</p>}
        {result.forecast.interval_observed_coverage != null && <p className="case-evaluation-note">Model interval: {percentage(result.forecast.interval_observed_coverage)} measured coverage{result.forecast.interval_nominal_coverage != null ? ` against ${percentage(result.forecast.interval_nominal_coverage)} nominal coverage` : ''}. Interval coverage is not the probability of a disruption.</p>}
        {!!Object.keys(result.forecast.by_horizon ?? {}).length && <details className="horizon-details"><summary>Inspect errors by forecast horizon</summary><div className="table-wrap"><table><thead><tr><th>Horizon</th><th>Method</th><th>MAE</th><th>RMSE</th><th>Samples</th></tr></thead><tbody>{Object.entries(result.forecast.by_horizon ?? {}).flatMap(([horizon, methods]) => Object.entries(methods).map(([method, metric]) => <tr key={`${horizon}-${method}`}><td>{horizon} h</td><td>{readable(method)}</td><td>{fmtNum(metric.mae, 4)}</td><td>{fmtNum(metric.rmse, 4)}</td><td>{fmtNum(metric.samples)}</td></tr>))}</tbody></table></div></details>}
        <HistoricalForecastPlot forecast={result.forecast} times={times} />
      </div>
      {warning && <div className="case-evaluation-block warning-evaluation"><div className="evaluation-heading"><h4>Advance-warning evaluation</h4><span>{readable(warning.status)}</span></div><p className="case-evaluation-note">{warning.message}</p><p className="case-evaluation-note">Target: {readable(warning.target)} · {warning.horizon_hours}-hour lead horizon. Fitting a model does not establish useful prediction.</p>
        {warning.brier_skill_score != null && warning.brier_skill_score <= 0 && <div className="evaluation-skill-note"><Icon name="shield" size={17} /><span>The warning model did not outperform the reference Brier score on this held-out case. Positive predictive skill has not been demonstrated here.</span></div>}
        <div className="warning-score-grid">{[
          ['Brier score', fmtNum(warning.brier_score, 4)], ['Reference Brier score', fmtNum(warning.reference_brier_score, 4)], ['Brier skill score', fmtNum(warning.brier_skill_score, 4)],
          ['Warning precision', percentage(warning.precision)], ['Warning recall', percentage(warning.recall)], ['Mean warning lead', hours(warning.mean_warning_lead_hours)],
          ['Event onsets', fmtNum(warning.event_onsets)], ['Events warned in advance', fmtNum(warning.events_with_advance_warning)], ['False warning hours', fmtNum(warning.false_warning_hours, 2)],
        ].map(([name, value]) => <div key={name}><span>{name}</span><b>{value === '–' ? 'Unavailable' : value}</b></div>)}</div>
        {warning.threshold != null && <p className="case-evaluation-note">Decision threshold selected before test evaluation: {fmtNum(warning.threshold, 3)}. Brier score measures squared probability error; lower is better. Skill compares that error with the reference forecast.</p>}
        {!!warning.comparisons?.length && <div className="table-wrap"><table><thead><tr><th>Warning method</th><th>Brier score</th><th>Precision</th><th>Recall</th></tr></thead><tbody>{warning.comparisons.map((row) => <tr key={row.method}><td>{readable(row.method)}</td><td>{fmtNum(row.brier_score, 4)}</td><td>{percentage(row.precision)}</td><td>{percentage(row.recall)}</td></tr>)}</tbody></table></div>}
        <HistoricalWarningPlot warning={warning} />
      </div>}
      {!!result.limitations.length && <div className="evaluation-limitations"><h4>Evaluation limitations</h4><ul>{result.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div>}
      <details className="run-reproducibility"><summary>Inspect evaluation fingerprint</summary><p>Method: {result.method_version}</p><p>Dataset SHA-256: <code>{result.dataset_hash}</code></p>{result.id && <p>Evaluation record: {result.id}</p>}</details><ResearchArtifacts artifacts={result.artifacts} />{!result.artifacts?.length && <p className="case-evaluation-note">This stored evaluation has no download attached to your session. Re-evaluate the case to create a private evidence archive.</p>}
    </>}
  </section>;
}
