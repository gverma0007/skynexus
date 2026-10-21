import { useMemo, useState } from 'react';
import FlatMap from '../globe/FlatMap';
import { api } from '../lib/api';
import type { Satellite } from '../lib/api';
import { fmtDateTime, fmtNum } from '../lib/format';
import { downloadText, stamp, toCsv } from '../lib/download';
import { go } from '../lib/router';
import { usePoll } from '../lib/usePoll';
import { Empty, ErrorNote, Skeleton } from '../components/ui';

type SortKey = 'name' | 'alt' | 'speed';

export default function Satellites({ selected }: { selected: number | null }) {
  const sats = usePoll(api.satellites, 30_000);
  const [cat, setCat] = useState<string>('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'name', desc: false });
  const [limit, setLimit] = useState(100);

  const cats = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    for (const s of sats.data ?? []) {
      const e = m.get(s.category) ?? { label: s.category_label, n: 0 };
      e.n++;
      m.set(s.category, e);
    }
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
  }, [sats.data]);

  const rows = useMemo(() => {
    const ql = query.trim().toLowerCase();
    return (sats.data ?? [])
      .filter((s) => cat === 'all' || s.category === cat)
      .filter((s) => !ql || s.name.toLowerCase().includes(ql) || String(s.norad_id) === ql)
      .sort((a, b) => {
        const c = sort.key === 'name' ? a.name.localeCompare(b.name) : sort.key === 'alt' ? a.altitude_km - b.altitude_km : a.speed_km_s - b.speed_km_s;
        return sort.desc ? -c : c;
      });
  }, [sats.data, cat, query, sort]);

  const th = (key: SortKey, label: string, cls = '') => (
    <th className={cls} aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
      <button className="sort" onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : false }))}>
        {label}{sort.key === key ? (sort.desc ? ' ↓' : ' ↑') : ''}
      </button>
    </th>
  );

  const exportCsv = () => downloadText(`skynexus-satellites-${stamp()}.csv`, toCsv(rows.map((s) => ({
    norad_id: s.norad_id, name: s.name, type: s.category_label, lat: s.lat, lon: s.lon,
    altitude_km: s.altitude_km, speed_km_s: s.speed_km_s, over_region: s.region_name ?? '', time: s.timestamp,
  }))), 'text/csv');

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>Satellites</h1>
          <p>{fmtNum(sats.data?.length)} spacecraft, positioned live from their orbital elements with SGP4.</p>
        </div>
        <button className="btn" onClick={exportCsv} disabled={!rows.length}>Export CSV</button>
      </div>
      <div className="toolbar">
        <label className="search-field">
          <span className="sr-only">Search satellites</span>
          <input value={query} onChange={(e) => { setQuery(e.target.value); setLimit(100); }} placeholder="Search by name or NORAD ID" />
        </label>
        <button className={`chip ${cat === 'all' ? 'on' : ''}`} aria-pressed={cat === 'all'} onClick={() => setCat('all')}>All <em>{sats.data?.length ?? 0}</em></button>
        {cats.map(([k, v]) => (
          <button key={k} className={`chip ${cat === k ? 'on' : ''}`} aria-pressed={cat === k} onClick={() => setCat(k)}>{v.label} <em>{v.n}</em></button>
        ))}
      </div>
      {sats.error && <ErrorNote message={sats.error} onRetry={sats.refresh} />}
      <div className={`sat ${selected ? 'with-detail' : ''}`}>
        <section className="panel table-wrap">
          <table>
            <thead>
              <tr>
                {th('name', 'Name')}
                <th className="r hide-sm">NORAD</th>
                <th>Type</th>
                {th('alt', 'Altitude km', 'r')}
                {th('speed', 'Speed km/s', 'r hide-sm')}
                <th>Currently over</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((s: Satellite) => (
                <tr key={s.norad_id} className={`clickable ${s.norad_id === selected ? 'sel' : ''}`} onClick={() => go('satellites', s.norad_id)}>
                  <td className="w550"><a href={`#/satellites/${s.norad_id}`} onClick={(e) => e.stopPropagation()}>{s.name}</a></td>
                  <td className="r num muted hide-sm">{s.norad_id}</td>
                  <td>{s.category_label}</td>
                  <td className="r num">{fmtNum(s.altitude_km)}</td>
                  <td className="r num hide-sm">{fmtNum(s.speed_km_s, 2)}</td>
                  <td className={s.region_name ? '' : 'muted'}>{s.region_name ?? 'Outside monitored regions'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!sats.data && !sats.error && <div className="pad"><Skeleton rows={10} /></div>}
          {sats.data && rows.length === 0 && <Empty title="No satellites match">Try a different name, NORAD number or type.</Empty>}
          {rows.length > limit && (
            <div className="pad center"><button className="btn" onClick={() => setLimit((l) => l + 200)}>Show more ({rows.length - limit} left)</button></div>
          )}
        </section>
        {selected && <SatelliteDetailPanel norad={selected} />}
      </div>
    </div>
  );
}

function SatelliteDetailPanel({ norad }: { norad: number }) {
  const d = usePoll(() => api.satellite(norad), 30_000, [norad]);
  const [copied, setCopied] = useState(false);
  if (d.error) return <section className="panel pad"><ErrorNote message={d.error} onRetry={d.refresh} /></section>;
  if (!d.data) return <section className="panel pad"><Skeleton rows={6} /></section>;
  const s = d.data;
  const o = s.orbit;
  const heading = (() => {
    const i = s.track.findIndex((t) => t.offset_min >= 0);
    const a = s.track[i];
    const b = s.track[i + 1];
    if (!a || !b) return '';
    const ns = b.lat > a.lat ? 'north' : 'south';
    const dl = ((b.lon - a.lon + 540) % 360) - 180;
    return `${ns}-${dl > 0 ? 'east' : 'west'}`;
  })();
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${s.name}\n${o.tle_line1}\n${o.tle_line2}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };
  return (
    <section className="panel sat-detail" aria-label={`${s.name} details`}>
      <div className="dh">
        <div className="dh-top">
          <h2>{s.name}</h2>
          <button className="icon-btn" onClick={() => go('satellites')} aria-label="Close satellite details">×</button>
        </div>
        <p className="muted m0">
          {s.category_label}, NORAD {s.norad_id}. {s.region_name ? `Over ${s.region_name}` : 'Outside the monitored regions'}
          {heading ? `, moving ${heading}` : ''} at {fmtNum(s.position.speed_km_s, 2)} km/s.
        </p>
      </div>
      <FlatMap track={s.track} current={s.position} height={210} caption="Solid: last 90 min. Dashed: next 90 min." />
      <div className="kv">
        <div><span>Altitude now</span><b className="num">{fmtNum(s.position.alt_km)} km</b></div>
        <div><span>Orbital period</span><b className="num">{fmtNum(o.period_minutes, 1)} min</b></div>
        <div><span>Inclination</span><b className="num">{fmtNum(o.inclination_deg, 2)}°</b></div>
        <div><span>Eccentricity</span><b className="num">{o.eccentricity.toFixed(5)}</b></div>
        <div><span>Perigee / apogee</span><b className="num">{fmtNum(o.perigee_alt_km)} / {fmtNum(o.apogee_alt_km)} km</b></div>
        <div><span>Orbits per day</span><b className="num">{fmtNum(o.mean_motion_revs_per_day, 2)}</b></div>
      </div>
      <div className="tle-block">
        <div className="tle-head">
          <span className="small muted">Orbital elements (TLE){o.epoch ? `, epoch ${fmtDateTime(o.epoch)}` : ''}</span>
          <button className="btn small" onClick={copy}>{copied ? 'Copied' : 'Copy TLE'}</button>
        </div>
        <pre className="tle">{o.tle_line1}{'\n'}{o.tle_line2}</pre>
      </div>
    </section>
  );
}
