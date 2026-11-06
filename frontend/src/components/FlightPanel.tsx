import { api } from '../lib/api';
import { fmtNum, timeAgo } from '../lib/format';
import { usePoll } from '../lib/usePoll';
import FlatMap from '../globe/FlatMap';
import { Skeleton } from './ui';

export default function FlightPanel({ icao24, onClose }: { icao24: string; onClose: () => void }) {
  const flight = usePoll(() => api.flightDetail(icao24), 30_000, [icao24]);
  const f = flight.data;

  const statusColor = (status?: string) => {
    switch (status) {
      case 'significant_deviation': return 'var(--crit, #d32f2f)';
      case 'minor_deviation': return 'var(--elev, #f57c00)';
      default: return 'var(--calm, #2e7d32)';
    }
  };

  const statusLabel = (status?: string) => {
    switch (status) {
      case 'significant_deviation': return 'Significant Deviation';
      case 'minor_deviation': return 'Minor Deviation';
      default: return 'On Route';
    }
  };

  const trackPoints = f?.route?.waypoints ?? [];
  const currentPt = f ? { lat: f.lat, lon: f.lon } : null;

  return (
    <div className="detail">
      <div className="dh">
        <div className="dh-top">
          <h2>
            <span className="lg-tick" style={{ display: 'inline-block', marginRight: 8 }} />
            {f?.callsign?.trim() || icao24.toUpperCase()}
          </h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close flight details">×</button>
        </div>
        {f && (
          <div className="score">
            <b className="num" style={{ fontSize: '1.25rem' }}>
              {f.route ? `${f.route.origin.iata} → ${f.route.dest.iata}` : 'En Route'}
            </b>
            <div>
              <span className="badge" style={{ background: statusColor(f.deviation?.status), color: '#fff', padding: '2px 8px', borderRadius: 4, fontSize: '0.75rem', fontWeight: 600 }}>
                {statusLabel(f.deviation?.status)}
              </span>
            </div>
          </div>
        )}
      </div>

      {!f && !flight.error && <div className="pad"><Skeleton rows={6} /></div>}
      {flight.error && <div className="pad muted small">Flight {icao24} position is no longer active in the current window.</div>}

      {f && (
        <>
          <div className="sec">
            <h4>Planned General Route vs Actual Position</h4>
            {f.route ? (
              <FlatMap
                track={trackPoints}
                current={currentPt}
                height={180}
                caption={`Solid line: general corridor ${f.route.origin.iata} (${f.route.origin.name}) → ${f.route.dest.iata} (${f.route.dest.name}). Dot: current aircraft position.`}
              />
            ) : (
              <p className="muted small m0">Route endpoint context unavailable for this regional probe.</p>
            )}
          </div>

          <div className="sec">
            <h4>Route Deviation Metrics</h4>
            {f.deviation ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px' }}>
                <div>
                  <span className="muted small block">Cross-track deviation</span>
                  <strong className="num" style={{ color: statusColor(f.deviation.status) }}>
                    {Math.abs(f.deviation.cross_track_km)} km ({Math.abs(f.deviation.cross_track_nm)} nm) {f.deviation.side}
                  </strong>
                </div>
                <div>
                  <span className="muted small block">Heading deviation</span>
                  <strong className="num">
                    {f.deviation.heading_deviation_deg > 0 ? `+${f.deviation.heading_deviation_deg}°` : `${f.deviation.heading_deviation_deg}°`}
                  </strong>
                </div>
                <div>
                  <span className="muted small block">Route progress</span>
                  <strong className="num">{f.deviation.progress_pct}%</strong>
                </div>
                <div>
                  <span className="muted small block">Total route distance</span>
                  <strong className="num">{fmtNum(f.deviation.total_route_km)} km</strong>
                </div>
              </div>
            ) : (
              <p className="muted small m0">No route deviation data available.</p>
            )}
            {f.summary && (
              <p className="small muted" style={{ marginTop: 8, lineHeight: 1.4 }}>
                {f.summary}
              </p>
            )}
          </div>

          <div className="sec">
            <h4>Telemetry & Navigation</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px' }}>
              <div>
                <span className="muted small block">Altitude</span>
                <strong className="num">{fmtNum(f.altitude_ft)} ft</strong>
              </div>
              <div>
                <span className="muted small block">Ground speed</span>
                <strong className="num">{fmtNum(f.speed_kt)} kt</strong>
              </div>
              <div>
                <span className="muted small block">Heading</span>
                <strong className="num">{f.heading_deg}°</strong>
              </div>
              <div>
                <span className="muted small block">Position</span>
                <span className="small">{f.lat.toFixed(2)}°, {f.lon.toFixed(2)}°</span>
              </div>
            </div>
            {f.region_name && (
              <p className="small muted m0" style={{ marginTop: 8 }}>
                Monitored zone: <b>{f.region_name}</b> ({timeAgo(f.timestamp)})
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

