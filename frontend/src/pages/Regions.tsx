import { useMemo, useState } from 'react';
import type { Region } from '../lib/api';
import { STATUS_LEVEL, fmtNum, fmtPct } from '../lib/format';
import { downloadText, stamp, toCsv } from '../lib/download';
import { go } from '../lib/router';
import { useSetStore, watchlist } from '../lib/store';
import { Bar, Empty, ErrorNote, Skeleton, Sparkline, StatusBadge, Swatch } from '../components/ui';

type SortKey = 'name' | 'index' | 'traffic' | 'quakes' | 'storm' | 'change';
type Filter = 'all' | 'watch' | 'attention';

const MAX_COMPARE = 3;

function signed(v: number): string {
  const r = Math.round(v);
  return r > 0 ? `+${r}` : String(r === 0 ? 0 : r);
}

export default function Regions({ regions, error }: { regions: Region[] | null; error: string | null }) {
  const watched = useSetStore(watchlist);
  const [filter, setFilter] = useState<Filter>('all');
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'index', desc: true });
  const [compare, setCompare] = useState<string[]>([]);

  const rows = useMemo(() => {
    const val = (r: Region): number | string => {
      switch (sort.key) {
        case 'name': return r.region_name;
        case 'traffic': return r.components.flights.pct_change ?? 0;
        case 'quakes': return r.components.events.count_24h;
        case 'storm': return r.components.weather.storm_now ?? 0;
        case 'change': return r.change_24h ?? 0;
        default: return r.composite_index;
      }
    };
    return (regions ?? [])
      .filter((r) => filter === 'all' || (filter === 'watch' ? watched.has(r.region_id) : STATUS_LEVEL[r.status] >= 2))
      .sort((a, b) => {
        const A = val(a), B = val(b);
        const c = typeof A === 'string' ? A.localeCompare(B as string) : (A as number) - (B as number);
        return sort.desc ? -c : c;
      });
  }, [regions, filter, sort, watched]);

  const counts = {
    all: regions?.length ?? 0,
    watch: regions?.filter((r) => watched.has(r.region_id)).length ?? 0,
    attention: regions?.filter((r) => STATUS_LEVEL[r.status] >= 2).length ?? 0,
  };

  const th = (key: SortKey, label: string, cls = '') => (
    <th className={cls} aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}>
      <button className="sort" onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== 'name' }))}>
        {label}{sort.key === key ? (sort.desc ? ' ↓' : ' ↑') : ''}
      </button>
    </th>
  );

  const toggleCompare = (id: string) =>
    setCompare((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= MAX_COMPARE ? [...c.slice(1), id] : [...c, id]));

  const exportCsv = () => {
    downloadText(`skynexus-regions-${stamp()}.csv`, toCsv(rows.map((r) => ({
      region: r.region_name, status: r.status, index: r.composite_index, change_24h: r.change_24h,
      air_traffic_score: r.flight_anomaly_score, air_traffic_vs_normal_pct: r.components.flights.pct_change,
      aircraft_per_hour: r.components.flights.recent, earthquakes_24h: r.components.events.count_24h,
      largest_magnitude: r.components.events.max_magnitude, storm_index: r.components.weather.storm_now,
    }))), 'text/csv');
  };

  const compared = (regions ?? []).filter((r) => compare.includes(r.region_id));

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>Regions</h1>
          <p>{counts.all} monitored zones, each compared with its own normal for the time of day.</p>
        </div>
        <div className="row-gap">
          {(['all', 'watch', 'attention'] as Filter[]).map((f) => (
            <button key={f} className={`chip ${filter === f ? 'on' : ''}`} aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : f === 'watch' ? 'Watchlist' : 'Needs attention'} <em>{counts[f]}</em>
            </button>
          ))}
          <button className="btn" onClick={exportCsv} disabled={!rows.length}>Export CSV</button>
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th className="w36"><span className="sr-only">Watchlist</span></th>
              {th('name', 'Region')}
              <th>Status</th>
              {th('index', 'Index', 'r')}
              {th('change', 'Change 24 h', 'r hide-sm')}
              {th('traffic', 'Air traffic vs normal')}
              {th('quakes', 'Earthquakes 24 h', 'r hide-sm')}
              {th('storm', 'Storm', 'r hide-sm')}
              <th className="hide-sm">Last 24 h</th>
              <th className="w70">Compare</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const f = r.components.flights;
              const isOn = watched.has(r.region_id);
              return (
                <tr key={r.region_id} className={compare.includes(r.region_id) ? 'sel' : ''}>
                  <td>
                    <button className={`star ${isOn ? 'on' : ''}`} onClick={() => watchlist.toggle(r.region_id)}
                      aria-label={`${isOn ? 'Remove' : 'Add'} ${r.region_name} ${isOn ? 'from' : 'to'} watchlist`} aria-pressed={isOn}>
                      {isOn ? '★' : '☆'}
                    </button>
                  </td>
                  <td>
                    <a className="rname" href={`#/overview/${r.region_id}`}><Swatch level={STATUS_LEVEL[r.status]} />{r.region_name}</a>
                  </td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="r num w600">{Math.round(r.composite_index)}</td>
                  <td className="r num hide-sm">{r.change_24h === null ? '–' : signed(r.change_24h)}</td>
                  <td>
                    <span className="mbar"><i style={{ width: `${r.flight_anomaly_score}%` }} /></span>
                    <span className="num small">{f.warming_up ? 'building baseline' : f.pct_change === null || f.score === 0 ? 'normal' : fmtPct(f.pct_change)}</span>
                  </td>
                  <td className="r num hide-sm">{r.components.events.count_24h}{r.components.events.max_magnitude ? <span className="muted small"> (max M{r.components.events.max_magnitude.toFixed(1)})</span> : null}</td>
                  <td className="r num hide-sm">{fmtNum(r.components.weather.storm_now)}</td>
                  <td className="hide-sm"><Sparkline values={r.sparkline} width={80} strong={STATUS_LEVEL[r.status] >= 2} /></td>
                  <td>
                    <input type="checkbox" checked={compare.includes(r.region_id)} onChange={() => toggleCompare(r.region_id)}
                      aria-label={`Compare ${r.region_name}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!regions && !error && <div className="pad"><Skeleton rows={8} /></div>}
        {regions && rows.length === 0 && (
          <Empty title={filter === 'watch' ? 'Your watchlist is empty' : 'No regions need attention'}>
            {filter === 'watch' ? 'Use the star next to a region to add it.' : 'Every region is calm or on watch right now.'}
          </Empty>
        )}
      </section>

      <section className="panel mt16">
        <div className="ph">
          <h3>{compared.length >= 2 ? `Comparing ${compared.map((r) => r.region_name).join(', ')}` : 'Compare regions'}</h3>
          {compared.length > 0 && <button className="btn small" onClick={() => setCompare([])}>Clear</button>}
        </div>
        {compared.length < 2 ? (
          <p className="muted pad m0">Tick Compare on two or three regions to see them side by side.</p>
        ) : (
          <div className="cmp" style={{ gridTemplateColumns: `repeat(${compared.length}, 1fr)` }}>
            {compared.map((r) => (
              <div key={r.region_id}>
                <div className="cmp-head"><b>{r.region_name}</b><StatusBadge status={r.status} /></div>
                <div className="score sm"><b className="num">{Math.round(r.composite_index)}</b></div>
                <Bar label="Air traffic" value={r.flight_anomaly_score} display={r.components.flights.pct_change === null ? '–' : fmtPct(r.components.flights.pct_change)} />
                <Bar label="Earthquakes" value={r.event_relevance_score} display={String(r.components.events.count_24h)} />
                <Bar label="Storm" value={r.weather_score} display={fmtNum(r.components.weather.storm_now)} />
                {r.satellite_score !== undefined && (
                  <Bar label="Satellites" value={r.satellite_score} display={`${r.components?.satellites?.count ?? 0} sat`} />
                )}
                <p className="small muted">{r.explanation[0]}</p>
                <div className="row-gap">
                  <button className="btn small" onClick={() => go('overview', r.region_id)}>Open on globe</button>
                  <button className="btn small" onClick={() => go('reports', null, { region: r.region_id, hours: '24', run: '1' })}>What changed</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
