import { api } from '../lib/api';
import type { Region } from '../lib/api';
import { fmtChange, fmtNum, plural, timeAgo, STATUS_LEVEL } from '../lib/format';
import { go } from '../lib/router';
import { useSetStore, watchlist } from '../lib/store';
import { usePoll } from '../lib/usePoll';
import TrafficChart from './TrafficChart';
import { Bar, Diamond, Empty, StatusBadge, Swatch } from './ui';

export default function RegionPanel({ region, onClose }: { region: Region; onClose: () => void }) {
  const id = region.region_id;
  const history = usePoll(() => api.history(id, 48), 120_000, [id]);
  const forecast = usePoll(() => api.forecast(id), 120_000, [id]);
  const overhead = usePoll(() => api.overhead(id), 30_000, [id]);
  const events = usePoll(() => api.events({ region_id: id, days: 2 }), 120_000, [id]);
  const anomalies = usePoll(() => api.anomalies({ region_id: id, hours: 24 }), 120_000, [id]);
  const watched = useSetStore(watchlist).has(id);
  const f = region.components.flights;
  const level = STATUS_LEVEL[region.status];

  const devs = f.route_deviations;
  const devLabel = devs?.significant_count
    ? `${devs.significant_count} diverting`
    : devs?.minor_count
      ? `${devs.minor_count} minor dev`
      : 'nominal';

  return (
    <div className="detail">
      <div className="dh">
        <div className="dh-top">
          <h2><Swatch level={level} />{region.region_name}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close region details">×</button>
        </div>
        <div className="score">
          <b className="num">{Math.round(region.composite_index)}</b>
          <div>
            <StatusBadge status={region.status} />
            <span className="muted small block">{fmtChange(region.change_24h)}</span>
          </div>
        </div>
      </div>

      <div className="sec">
        <h4>What is driving the score</h4>
        <Bar label="Flight route deviation" value={region.flight_anomaly_score} display={devLabel}
          hint="Cross-track route deviation of active flights from planned general travel corridors." />
        <Bar label="War & Conflict risk" value={region.event_relevance_score}
          hint="Predicted conflict threat and security incidents from orbital surveillance and corridor avoidance." />
        <Bar label="Storm intensity" value={region.weather_score}
          hint="Storm index from wind, gusts and rain at the region centre." />
        {region.satellite_score !== undefined && (
          <Bar label="Satellite density & coverage" value={region.satellite_score}
            display={`${region.components?.satellites?.count ?? 0} overhead`}
            hint="Satellite density change vs baseline, surveillance passes (LEO) and navigation geometry (GNSS)." />
        )}
        <ul className="explain">
          {region.explanation.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>

      <div className="sec">
        <h4 className="h4-row">Aircraft per hour <span className="muted small">last 48 h and next 6 h</span></h4>
        {history.data ? (
          <TrafficChart points={history.data.points} forecast={forecast.data} />
        ) : (
          <div className="chart-empty">{history.error ?? 'Loading chart…'}</div>
        )}
      </div>

      <div className="sec">
        <h4>Conflict & Security Incidents</h4>
        {events.data && events.data.length > 0 ? (
          events.data.slice(0, 4).map((e) => (
            <div className="ev" key={e.id}>
              <Diamond mag={e.magnitude} />
              <span>{(e.description ?? e.event_type).replace(' earthquake — ', ', ').replace(/^M[\d.]+ earthquake — /, 'Incident: ')}</span>
              <span className="muted small nowrap">{timeAgo(e.event_date)}</span>
            </div>
          ))
        ) : (
          <p className="muted small m0">{events.data ? 'None in the last 48 hours.' : 'Loading…'}</p>
        )}
      </div>

      {anomalies.data && anomalies.data.length > 0 && (
        <div className="sec">
          <h4>Unusual hours flagged by the anomaly model</h4>
          {anomalies.data.slice(0, 3).map((a) => (
            <div className="ev" key={a.id}>
              <span className={`sev-dot s-${a.severity_label}`} aria-hidden="true" />
              <span>{a.summary}</span>
              <span className="muted small nowrap">{timeAgo(a.timestamp)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="sec">
        <h4>Overhead right now</h4>
        {overhead.data ? (
          overhead.data.count === 0 ? (
            <p className="muted m0">No tracked satellites are over this region at the moment.</p>
          ) : (
            <>
              <p className="m0">
                {plural(overhead.data.count, 'satellite')}
                <span className="muted">
                  {' '}({Object.entries(overhead.data.by_category).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(', ')})
                </span>
              </p>
              <div className="sat-chips">
                {overhead.data.satellites.slice(0, 6).map((s) => (
                  <a key={s.norad_id} className="chip" href={`#/satellites/${s.norad_id}`}>{s.name}</a>
                ))}
              </div>
            </>
          )
        ) : (
          <p className="muted small m0">Loading…</p>
        )}
      </div>

      <div className="actions">
        <button className="btn primary" onClick={() => go('reports', null, { region: id, hours: '24', run: '1' })}>
          Compare last 24 h
        </button>
        <button className="btn" onClick={() => watchlist.toggle(id)} aria-pressed={watched}>
          {watched ? '★ On watchlist' : '☆ Add to watchlist'}
        </button>
      </div>
      {f.baseline_days < 7 && (
        <p className="note">
          Based on {fmtNum(f.baseline_days, 1)} days of air-traffic history. Scores become more reliable as a full week builds up.
        </p>
      )}
      {!region.explanation.length && <Empty title="No details yet" />}
    </div>
  );
}
