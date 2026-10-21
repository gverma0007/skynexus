import { useMemo, useState } from 'react';
import FlatMap from '../globe/FlatMap';
import { api } from '../lib/api';
import type { Outline, Region } from '../lib/api';
import { fmtDateTime, fmtNum, timeAgo } from '../lib/format';
import { downloadText, stamp, toCsv } from '../lib/download';
import { go } from '../lib/router';
import { usePoll } from '../lib/usePoll';
import { Diamond, Empty, ErrorNote, Skeleton } from '../components/ui';

type Tab = 'quakes' | 'anomalies';

export default function Events({ regions, outlines, tab }: { regions: Region[] | null; outlines: Outline[] | null; tab: Tab }) {
  const [days, setDays] = useState(7);
  const [minMag, setMinMag] = useState(0);
  const [region, setRegion] = useState('');
  const [highlight, setHighlight] = useState<string | null>(null);
  const events = usePoll(() => api.events({ days, min_magnitude: minMag, region_id: region || undefined }), 120_000, [days, minMag, region]);
  const anomalies = usePoll(() => api.anomalies({ hours: days * 24, region_id: region || undefined }), 120_000, [days, region]);

  const groups = useMemo(() => {
    const m = new Map<string, NonNullable<typeof events.data>>();
    for (const e of events.data ?? []) {
      const k = new Date(e.event_date).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' });
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(e);
    }
    return [...m.entries()];
  }, [events.data]);

  const boxes = useMemo(() => (outlines ?? []).map((o) => ({ ring: o.ring, strong: o.id === region })), [outlines, region]);
  const dots = useMemo(() => (events.data ?? []).map((e) => ({ id: e.id, lat: e.lat, lon: e.lon, mag: e.magnitude })), [events.data]);

  const exportCsv = () => {
    if (tab === 'quakes') {
      downloadText(`skynexus-earthquakes-${stamp()}.csv`, toCsv((events.data ?? []).map((e) => ({
        time_utc: e.event_date, magnitude: e.magnitude, description: e.description, region: e.region_name,
        lat: e.lat, lon: e.lon, source: e.source,
      }))), 'text/csv');
    } else {
      downloadText(`skynexus-anomalies-${stamp()}.csv`, toCsv((anomalies.data ?? []).map((a) => ({
        hour_utc: a.timestamp, region: a.region_name, feature: a.feature_name, value: a.observed_value,
        z_score: a.z_score, isolation_forest: a.isolation_forest_score, composite: a.composite_score, severity: a.severity_label,
      }))), 'text/csv');
    }
  };

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>Events</h1>
          <p>Earthquakes inside the monitored regions, and the hours the anomaly model flagged as unusual.</p>
        </div>
        <button className="btn" onClick={exportCsv}>Export CSV</button>
      </div>
      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Event type">
          <button role="tab" aria-selected={tab === 'quakes'} className={tab === 'quakes' ? 'on' : ''} onClick={() => go('events')}>Earthquakes</button>
          <button role="tab" aria-selected={tab === 'anomalies'} className={tab === 'anomalies' ? 'on' : ''} onClick={() => go('events', 'anomalies')}>Anomaly log</button>
        </div>
        <label className="field">
          <span>Region</span>
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="">All regions</option>
            {(regions ?? []).slice().sort((a, b) => a.region_name.localeCompare(b.region_name)).map((r) => (
              <option key={r.region_id} value={r.region_id}>{r.region_name}</option>
            ))}
          </select>
        </label>
        <div className="seg" role="group" aria-label="Time range">
          {[1, 7, 30].map((d) => <button key={d} className={days === d ? 'on' : ''} aria-pressed={days === d} onClick={() => setDays(d)}>{d === 1 ? '24 h' : `${d} days`}</button>)}
        </div>
        {tab === 'quakes' && (
          <div className="seg" role="group" aria-label="Minimum magnitude">
            {[0, 4, 5].map((m) => <button key={m} className={minMag === m ? 'on' : ''} aria-pressed={minMag === m} onClick={() => setMinMag(m)}>{m === 0 ? 'Any size' : `M${m}+`}</button>)}
          </div>
        )}
      </div>

      {tab === 'quakes' ? (
        <div className="events-grid">
          <section className="panel">
            <FlatMap dots={dots} boxes={boxes} highlight={highlight} height={300} onDot={setHighlight}
              caption="Dashed boxes are monitored regions. Red diamonds are M5.5 or larger." />
          </section>
          <section className="panel ev-list" aria-label="Earthquake list">
            {events.error && <ErrorNote message={events.error} onRetry={events.refresh} />}
            {!events.data && !events.error && <div className="pad"><Skeleton rows={6} /></div>}
            {events.data && events.data.length === 0 && (
              <Empty title="No earthquakes match">Widen the time range or lower the magnitude filter.</Empty>
            )}
            {groups.map(([day, list]) => (
              <div key={day}>
                <h4 className="day">{day}</h4>
                {list.map((e) => (
                  <button key={e.id} className={`ev-row ${highlight === e.id ? 'sel' : ''}`} onClick={() => setHighlight(e.id)}>
                    <span className="mag num">M{e.magnitude.toFixed(1)}</span>
                    <Diamond mag={e.magnitude} />
                    <span className="grow">
                      {(e.description ?? e.event_type).replace(/^M[\d.]+ earthquake — /, '')}
                      <span className="block small muted">{e.region_name}</span>
                    </span>
                    <span className="small muted nowrap" title={fmtDateTime(e.event_date)}>{timeAgo(e.event_date)}</span>
                  </button>
                ))}
              </div>
            ))}
          </section>
        </div>
      ) : (
        <section className="panel table-wrap">
          <table>
            <thead>
              <tr><th>Hour</th><th>Region</th><th>What was unusual</th><th className="r">Z-score</th><th className="r hide-sm">Isolation Forest</th><th className="r">Score</th></tr>
            </thead>
            <tbody>
              {(anomalies.data ?? []).map((a) => (
                <tr key={a.id} className="clickable" onClick={() => go('overview', a.region_id)}>
                  <td className="nowrap">{fmtDateTime(a.timestamp)}</td>
                  <td className="w550">{a.region_name}</td>
                  <td>{a.summary}</td>
                  <td className="r num">{fmtNum(a.z_score, 1)}</td>
                  <td className="r num hide-sm">{fmtNum(a.isolation_forest_score)}</td>
                  <td className="r"><span className={`score-pill s-${a.severity_label}`}>{fmtNum(a.composite_score)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {anomalies.error && <ErrorNote message={anomalies.error} onRetry={anomalies.refresh} />}
          {anomalies.data && anomalies.data.length === 0 && (
            <Empty title="Nothing unusual flagged">The model needs at least a day of history per region before it can flag hours.</Empty>
          )}
          <p className="note">
            Each hour is scored against the region's earlier hours with a z-score and an Isolation Forest. Only hours scoring 50 or more, with a z-score of at least 2 or a strong Isolation Forest score, are kept.
            A traffic drop during a storm is marked as weather-explained.
          </p>
        </section>
      )}
    </div>
  );
}
