import { useMemo, useState } from 'react';
import Globe from '../globe/Globe';
import { ringToPolygon } from '../globe/draw';
import type { GlobeEvent, GlobeFlight, GlobeRegion, GlobeSat, Layers } from '../globe/draw';
import { api } from '../lib/api';
import type { Outline, Region } from '../lib/api';
import { STATUS_LEVEL, fmtNum, timeAgo } from '../lib/format';
import { go } from '../lib/router';
import { useSetStore, watchlist } from '../lib/store';
import { usePoll } from '../lib/usePoll';
import RegionPanel from '../components/RegionPanel';
import { Diamond, Empty, ErrorNote, Skeleton, Sparkline, Swatch } from '../components/ui';

interface Props {
  regions: Region[] | null;
  regionsError: string | null;
  outlines: Outline[] | null;
  selectedId: string | null;
}

const LEGEND: { label: string; level: 0 | 1 | 2 | 3 }[] = [
  { label: 'Calm', level: 0 }, { label: 'Watch', level: 1 }, { label: 'Elevated', level: 2 }, { label: 'Critical', level: 3 },
];

export function headline(regions: Region[]): { title: string; sub: string } {
  const crit = regions.filter((r) => r.status === 'Critical');
  const elev = regions.filter((r) => r.status === 'Elevated');
  const n = crit.length + elev.length;
  const others = regions.length - n;
  if (n === 0) {
    const top = regions[0];
    return {
      title: `All ${regions.length} regions are within normal ranges`,
      sub: top ? `The highest score is ${top.region_name} at ${Math.round(top.composite_index)} of 100.` : '',
    };
  }
  const names = (rs: Region[]) => rs.map((r) => r.region_name).join(' and ');
  const parts = [];
  if (crit.length) parts.push(`${names(crit)} ${crit.length > 1 ? 'are' : 'is'} critical`);
  if (elev.length) parts.push(`${names(elev)} ${elev.length > 1 ? 'are' : 'is'} elevated`);
  return {
    title: `${n} region${n > 1 ? 's need' : ' needs'} attention`,
    sub: `${parts.join(' and ')}. The other ${others} ${others === 1 ? 'is' : 'are'} calm or on watch.`,
  };
}

export default function Overview({ regions, regionsError, outlines, selectedId }: Props) {
  const flights = usePoll(api.flights, 60_000);
  const sats = usePoll(api.satellites, 30_000);
  const events = usePoll(() => api.events({ days: 2 }), 120_000);
  const [layers, setLayers] = useState<Layers>({ aircraft: true, satellites: true, events: true, outlines: true });
  const [filter, setFilter] = useState<'all' | 'watch'>('all');
  const watched = useSetStore(watchlist);

  const selected = regions?.find((r) => r.region_id === selectedId) ?? null;
  const select = (id: string | null) => go('overview', id);

  const globeRegions: GlobeRegion[] = useMemo(() => {
    if (!outlines || !regions) return [];
    const byId = new Map(regions.map((r) => [r.region_id, r]));
    return outlines.map((o) => {
      const r = byId.get(o.id);
      return {
        id: o.id, name: o.name, lat: r?.lat ?? 0, lon: r?.lon ?? 0,
        score: r?.composite_index ?? 0, level: r ? STATUS_LEVEL[r.status] : 0, polygon: ringToPolygon(o.ring),
      };
    });
  }, [outlines, regions]);

  const gFlights: GlobeFlight[] = useMemo(() => (flights.data ?? []).map((f) => ({
    id: f.icao24, lat: f.lat, lon: f.lon, heading: f.heading_deg,
    label: `${f.callsign.trim() || f.icao24}, ${fmtNum(f.altitude_ft)} ft, ${fmtNum(f.speed_kt)} kt`,
  })), [flights.data]);
  const gSats: GlobeSat[] = useMemo(() => (sats.data ?? []).map((s) => ({
    id: s.norad_id, lat: s.lat, lon: s.lon, label: `${s.name}, ${fmtNum(s.altitude_km)} km`,
  })), [sats.data]);
  const gEvents: GlobeEvent[] = useMemo(() => (events.data ?? []).map((e) => ({
    id: e.id, lat: e.lat, lon: e.lon, mag: e.magnitude,
    label: `${(e.description ?? e.event_type).replace(' earthquake — ', ', ')}, ${timeAgo(e.event_date)}`,
  })), [events.data]);

  const focus = selected ? { lat: selected.lat, lon: selected.lon, key: selected.region_id } : null;
  const list = (regions ?? []).filter((r) => filter === 'all' || watched.has(r.region_id));
  const hl = regions ? headline(regions) : null;

  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));

  return (
    <div className={`ov ${selected ? 'has-sel' : ''}`}>
      <section className="panel ov-left" aria-label="Regions">
        <div className="headline">
          {hl ? (<><h1>{hl.title}</h1><p>{hl.sub}</p></>) : regionsError ? null : <Skeleton rows={3} />}
          {regionsError && <ErrorNote message={regionsError} />}
        </div>
        <div className="ph">
          <div className="seg small" role="tablist" aria-label="Filter regions">
            <button role="tab" aria-selected={filter === 'all'} className={filter === 'all' ? 'on' : ''} onClick={() => setFilter('all')}>All regions</button>
            <button role="tab" aria-selected={filter === 'watch'} className={filter === 'watch' ? 'on' : ''} onClick={() => setFilter('watch')}>Watchlist {watched.size > 0 && <em>{watched.size}</em>}</button>
          </div>
          <span className="ph-aside">Index 0–100</span>
        </div>
        <div className="rlist">
          {list.map((r) => (
            <button key={r.region_id} className={`rrow ${r.region_id === selectedId ? 'sel' : ''}`}
              onClick={() => select(r.region_id === selectedId ? null : r.region_id)}
              aria-pressed={r.region_id === selectedId}>
              <Swatch level={STATUS_LEVEL[r.status]} title={r.status} />
              <span className="n">{r.region_name}{watched.has(r.region_id) && <span className="star-mini" aria-label="on watchlist">★</span>}</span>
              <Sparkline values={r.sparkline} strong={STATUS_LEVEL[r.status] >= 2} />
              <span className="v num">{Math.round(r.composite_index)}</span>
            </button>
          ))}
          {regions && filter === 'watch' && list.length === 0 && (
            <Empty title="Your watchlist is empty">Open a region and choose Add to watchlist to keep it here.</Empty>
          )}
          {!regions && !regionsError && <Skeleton rows={8} />}
        </div>
      </section>

      <section className="panel globewrap" aria-label="Globe">
        <Globe regions={globeRegions} flights={gFlights} sats={gSats} events={gEvents} layers={layers}
          selectedRegion={selectedId} selectedSat={null} focus={focus}
          onSelectRegion={(id) => select(id)} onSelectSat={(id) => go('satellites', id)} />
        <div className="legend" aria-label="Legend">
          {LEGEND.map((l) => <div key={l.label}><Swatch level={l.level} />{l.label}</div>)}
          <div className="legend-sep" />
          <div><span className="lg-tick" />Aircraft</div>
          <div><span className="lg-ring" />Satellite</div>
          <div><span className="dia" />Earthquake</div>
        </div>
        <div className="layers" role="group" aria-label="Layers">
          <button className={`chip ${layers.aircraft ? 'on' : ''}`} aria-pressed={layers.aircraft} onClick={() => toggle('aircraft')}>
            Aircraft <em>{fmtNum(flights.data?.length)}</em>
          </button>
          <button className={`chip ${layers.satellites ? 'on' : ''}`} aria-pressed={layers.satellites} onClick={() => toggle('satellites')}>
            Satellites <em>{fmtNum(sats.data?.length)}</em>
          </button>
          <button className={`chip ${layers.events ? 'on' : ''}`} aria-pressed={layers.events} onClick={() => toggle('events')}>
            Earthquakes <em>{fmtNum(events.data?.length)}</em>
          </button>
          <button className={`chip ${layers.outlines ? 'on' : ''}`} aria-pressed={layers.outlines} onClick={() => toggle('outlines')}>
            Regions
          </button>
        </div>
        <p className="globe-hint">Drag to rotate, scroll to zoom, click a region or satellite.</p>
      </section>

      <section className="panel ov-right" aria-label="Details">
        {selected ? (
          <RegionPanel key={selected.region_id} region={selected} onClose={() => select(null)} />
        ) : (
          <WorldPanel regions={regions} events={events.data} />
        )}
      </section>
    </div>
  );
}

function WorldPanel({ regions, events }: { regions: Region[] | null; events: { id: string; magnitude: number; description: string | null; event_type: string; event_date: string; region_name: string }[] | null }) {
  const anomalies = usePoll(() => api.anomalies({ hours: 24 }), 120_000);
  const movers = (regions ?? [])
    .filter((r) => r.change_24h !== null)
    .sort((a, b) => Math.abs(b.change_24h!) - Math.abs(a.change_24h!))
    .slice(0, 4);
  return (
    <div className="detail">
      <div className="dh">
        <h2>World summary</h2>
        <p className="muted m0">Select a region on the globe or in the list for its full breakdown.</p>
      </div>
      <div className="sec">
        <h4>Biggest changes since yesterday</h4>
        {movers.length ? movers.map((r) => (
          <button key={r.region_id} className="mover" onClick={() => go('overview', r.region_id)}>
            <Swatch level={STATUS_LEVEL[r.status]} />
            <span>{r.region_name}</span>
            <span className="num">{Math.round(r.change_24h!) > 0 ? '+' : ''}{Math.round(r.change_24h!) || 0}</span>
          </button>
        )) : <p className="muted small m0">Comparisons appear after two days of data.</p>}
      </div>
      <div className="sec">
        <h4>Unusual hours, last 24 h</h4>
        {anomalies.data?.length ? anomalies.data.slice(0, 5).map((a) => (
          <button key={a.id} className="ev ev-btn" onClick={() => go('overview', a.region_id)}>
            <span className={`sev-dot s-${a.severity_label}`} aria-hidden="true" />
            <span><b className="w550">{a.region_name}.</b> {a.summary}</span>
            <span className="muted small nowrap">{timeAgo(a.timestamp)}</span>
          </button>
        )) : <p className="muted small m0">{anomalies.data ? 'Nothing unusual flagged.' : 'Loading…'}</p>}
      </div>
      <div className="sec">
        <h4>Latest earthquakes</h4>
        {events?.length ? events.slice(0, 5).map((e) => (
          <div className="ev" key={e.id}>
            <Diamond mag={e.magnitude} />
            <span>{(e.description ?? e.event_type).replace(' earthquake — ', ', ')} <span className="muted">({e.region_name})</span></span>
            <span className="muted small nowrap">{timeAgo(e.event_date)}</span>
          </div>
        )) : <p className="muted small m0">{events ? 'None inside monitored regions.' : 'Loading…'}</p>}
      </div>
    </div>
  );
}
