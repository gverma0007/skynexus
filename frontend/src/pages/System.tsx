import { useState } from 'react';
import { api } from '../lib/api';
import { fmtDuration, fmtNum, timeAgo } from '../lib/format';
import { usePoll } from '../lib/usePoll';
import { ErrorNote, Skeleton } from '../components/ui';

export default function System() {
  const [fast, setFast] = useState(false);
  const h = usePoll(api.system, fast ? 3_000 : 30_000, [fast]);
  const [msg, setMsg] = useState<string | null>(null);

  const run = async () => {
    setMsg(null);
    try {
      const r = await api.runIngest();
      setMsg(r.status === 'started' ? 'Ingest started. This page updates when it finishes.' : 'An ingest cycle is already running.');
      setFast(true);
      setTimeout(() => setFast(false), 180_000);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Could not start ingest');
    }
  };

  if (h.error && !h.data) return <div className="page"><ErrorNote message={h.error} onRetry={h.refresh} /></div>;
  if (!h.data) return <div className="page"><Skeleton rows={8} /></div>;
  const d = h.data;
  const st = d.ingest;
  const isDemo = d.data_mode === 'demo';

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>System</h1>
          <p>Where the data comes from and whether it is arriving.</p>
        </div>
        <button className="btn primary" onClick={run} disabled={st.running}>
          {st.running ? 'Running…' : isDemo ? 'Rerun analysis now' : 'Run ingest now'}
        </button>
      </div>
      {msg && <p className="note mb16" role="status">{msg}</p>}

      <div className="facts">
        <div className="panel fact">
          <span>Data mode</span>
          <b>{isDemo ? 'Demo world' : 'Live feeds'}</b>
          <p>{isDemo ? 'Generated 8-day dataset. Set DATA_MODE=live in .env for real feeds.' : `Ingests every ${fmtDuration(d.ingest_interval_s)}${d.live_ingest ? '' : ' (loop disabled)'}.`}</p>
        </div>
        <div className="panel fact">
          <span>Report text</span>
          <b>{d.ai_mode === 'claude' ? 'Claude' : 'Built-in template'}</b>
          <p>{d.ai_mode === 'claude' ? `Model ${d.ai_model}.` : 'Add ANTHROPIC_API_KEY to .env for AI-written assessments.'}</p>
        </div>
        <div className="panel fact">
          <span>Last cycle</span>
          <b>{st.running ? 'Running now' : st.last_finished ? timeAgo(st.last_finished) : 'Not yet run'}</b>
          <p>{st.last_error ? `Failed: ${st.last_error}` : st.duration_s ? `Took ${fmtNum(st.duration_s, 1)} s. ${st.cycles} cycle${st.cycles === 1 ? '' : 's'} since start.` : 'Starts automatically with the backend.'}</p>
        </div>
        <div className="panel fact">
          <span>Retention</span>
          <b>{d.retention_days} days</b>
          <p>Older observations are pruned each cycle.</p>
        </div>
      </div>

      <section className="panel table-wrap mt16">
        <div className="ph"><h3>Data sources</h3><span className="ph-aside">All free and key-less</span></div>
        <table>
          <thead><tr><th>Source</th><th>Provides</th><th>Status</th><th className="r">Rows, 24 h</th><th className="r hide-sm">Rows stored</th><th>Last data</th></tr></thead>
          <tbody>
            {d.sources.map((s) => (
              <tr key={`${s.domain}-${s.source}`}>
                <td className="w550">{s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.source}</a> : s.source}</td>
                <td>{s.name}<span className="block small muted">{s.description}</span></td>
                <td><span className={`health h-${s.status}`}>{s.status === 'ok' ? 'Receiving' : s.status === 'demo' ? 'Demo data' : 'Not updating'}</span></td>
                <td className="r num">{fmtNum(s.rows_24h)}</td>
                <td className="r num hide-sm">{fmtNum(s.rows_total)}</td>
                <td className="nowrap">{timeAgo(s.last_seen)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {d.sources.length === 0 && <p className="muted pad m0">No data yet. The first ingest cycle takes one to two minutes.</p>}
      </section>

      {st.last_summary && (
        <section className="panel mt16">
          <div className="ph"><h3>Last cycle summary</h3></div>
          <div className="summary-grid">
            {Object.entries(st.last_summary).map(([k, v]) => (
              <div key={k}><span className="small muted">{k.replace(/_/g, ' ')}</span><b className="num">{v < 0 ? 'failed' : fmtNum(v)}</b></div>
            ))}
          </div>
        </section>
      )}

      <section className="panel mt16">
        <div className="ph"><h3>Stored totals</h3></div>
        <div className="summary-grid">
          {Object.entries(d.counts).map(([k, v]) => (
            <div key={k}><span className="small muted">{k}</span><b className="num">{fmtNum(v)}</b></div>
          ))}
        </div>
      </section>
    </div>
  );
}
