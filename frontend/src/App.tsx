import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from './lib/api';
import type { Alert, SearchResult, Stats } from './lib/api';
import { fmtNum, timeAgo } from './lib/format';
import { PAGES, go, href, useRoute } from './lib/router';
import { dismissedAlerts, useSetStore } from './lib/store';
import { usePoll } from './lib/usePoll';
import Overview from './pages/Overview';
import Regions from './pages/Regions';
import Satellites from './pages/Satellites';
import Events from './pages/Events';
import Reports from './pages/Reports';
import System from './pages/System';

export default function App() {
  const route = useRoute();
  const regions = usePoll(api.regions, 60_000);
  const outlines = usePoll(api.outlines, 0);
  const stats = usePoll(api.stats, 60_000);
  const [searchOpen, setSearchOpen] = useState(false);
  const [, tick] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      } else if (e.key === '/' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement)) {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    const t = setInterval(() => tick((n) => n + 1), 30_000); // refresh "x min ago" labels
    return () => {
      window.removeEventListener('keydown', onKey);
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    const page = PAGES.find((p) => p.id === route.page)?.label ?? 'Overview';
    document.title = `${page} · SkyNexus`;
  }, [route.page]);

  let body;
  switch (route.page) {
    case 'regions':
      body = <Regions regions={regions.data} error={regions.error} />;
      break;
    case 'satellites':
      body = <Satellites selected={route.id ? Number(route.id) : null} />;
      break;
    case 'events':
      body = <Events regions={regions.data} outlines={outlines.data} tab={route.id === 'anomalies' ? 'anomalies' : 'quakes'} />;
      break;
    case 'reports':
      body = <Reports regions={regions.data} reportId={route.id} params={route.params} />;
      break;
    case 'system':
      body = <System />;
      break;
    default:
      body = <Overview regions={regions.data} regionsError={regions.error} outlines={outlines.data} selectedId={route.id} />;
  }

  return (
    <div className={`app page-${route.page}`}>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <a className="brand" href={href('overview')} aria-label="SkyNexus home">
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
            <circle cx="11" cy="11" r="9.5" fill="none" stroke="#000" strokeWidth="1.6" />
            <ellipse cx="11" cy="11" rx="4" ry="9.5" fill="none" stroke="#000" strokeWidth="1.2" />
            <path d="M1.5 11h19" stroke="#000" strokeWidth="1.2" />
          </svg>
          SkyNexus
        </a>
        <nav className="nav" aria-label="Main">
          {PAGES.map((p) => (
            <a key={p.id} href={href(p.id)} className={route.page === p.id ? 'on' : ''} aria-current={route.page === p.id ? 'page' : undefined}>
              {p.label}
            </a>
          ))}
        </nav>
        <div className="right">
          <ModeSwitch
            mode={stats.data?.data_mode ?? 'live'}
            onSwitch={() => {
              stats.refresh();
              regions.refresh();
            }}
          />
          <button className="search" onClick={() => setSearchOpen(true)} aria-label="Search regions and satellites">
            <SearchIcon />
            <span className="search-text">Search regions or satellites</span>
            <span className="kbd">Ctrl K</span>
          </button>
          <AlertsMenu />
          <LiveBadge stats={stats.data} error={stats.error} />
        </div>
      </header>
      <StatusStrip stats={stats.data} />
      <main id="main">{body}</main>
      <footer className="foot no-print">
        SkyNexus measures statistical change in public data. Correlation does not establish causation.
      </footer>
      {searchOpen && <SearchPalette onClose={() => setSearchOpen(false)} />}
    </div>
  );
}

function ModeSwitch({ mode, onSwitch }: { mode: string; onSwitch: () => void }) {
  const [switching, setSwitching] = useState(false);
  const isDemo = mode === 'demo';

  const handleToggle = async (targetMode: 'live' | 'demo') => {
    if (targetMode === (isDemo ? 'demo' : 'live') || switching) return;
    setSwitching(true);
    try {
      await api.setMode(targetMode);
      onSwitch();
      setTimeout(() => {
        setSwitching(false);
        window.location.reload();
      }, 250);
    } catch {
      setSwitching(false);
    }
  };

  return (
    <div className="mode-switch" role="group" aria-label="Data source mode">
      <button
        type="button"
        className={`mode-btn ${!isDemo ? 'active' : ''}`}
        onClick={() => handleToggle('live')}
        disabled={switching}
        title="Switch to live real-time feeds"
      >
        <span className="dot live" />
        Live
      </button>
      <button
        type="button"
        className={`mode-btn ${isDemo ? 'active' : ''}`}
        onClick={() => handleToggle('demo')}
        disabled={switching}
        title="Switch to offline simulated demo dataset"
      >
        <span className="dot demo" />
        Demo
      </button>
    </div>
  );
}

function LiveBadge({ stats, error }: { stats: Stats | null; error: string | null }) {
  if (error) return <span className="live off" title={error}><b />Offline</span>;
  if (!stats) return <span className="live"><b />Connecting</span>;
  const demo = stats.data_mode === 'demo';
  return (
    <a className={`live ${demo ? 'demo' : ''}`} href={href('system')} title="Data sources and ingest status">
      <b />{demo ? 'Demo data' : 'Live'}, updated {timeAgo(stats.last_update)}
    </a>
  );
}

function StatusStrip({ stats }: { stats: Stats | null }) {
  if (!stats) return <div className="strip" aria-hidden="true">&nbsp;</div>;
  let next = '';
  if (stats.ingest_interval_s && stats.last_update && stats.data_mode === 'live') {
    const due = new Date(stats.last_update).getTime() + stats.ingest_interval_s * 1000 - Date.now();
    next = due > 60_000 ? `Next refresh in about ${Math.round(due / 60_000)} min` : 'Refreshing soon';
  }
  return (
    <div className="strip" role="status">
      <span><strong className="num">{fmtNum(stats.aircraft_now)}</strong>aircraft tracked</span>
      <span><strong className="num">{fmtNum(stats.satellites_tracked)}</strong>satellites</span>
      <span><strong className="num">{fmtNum(stats.events_24h)}</strong>earthquakes in 24 h</span>
      <span className="hide-sm"><strong className="num">{stats.regions_monitored}</strong>regions monitored</span>
      <span className="strip-end hide-sm">{next || (stats.data_mode === 'demo' ? 'Showing the generated demo world' : '')}</span>
    </div>
  );
}

function AlertsMenu() {
  const alerts = usePoll(api.alerts, 60_000);
  const dismissed = useSetStore(dismissedAlerts);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = useMemo(() => (alerts.data ?? []).filter((a) => !dismissed.has(a.id)), [alerts.data, dismissed]);
  const critical = active.some((a) => a.level === 'critical');

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);

  const openAlert = (a: Alert) => {
    setOpen(false);
    if (a.kind === 'system') go('system');
    else if (a.region_id) go('overview', a.region_id);
  };

  return (
    <div className="alerts" ref={ref}>
      <button className="bell" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={`Alerts, ${active.length} active`}>
        <svg width="15" height="15" viewBox="0 0 15 15" aria-hidden="true"><path d="M3 11V7a4.5 4.5 0 019 0v4l1 1H2zM6 13.5h3" fill="none" stroke="#000" strokeWidth="1.3" /></svg>
        {active.length > 0 && <i className={critical ? 'crit' : ''}>{active.length}</i>}
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Alerts">
          <div className="pop-head">
            <b>Alerts</b>
            {active.length > 0 && <button className="link" onClick={() => dismissedAlerts.add(active.map((a) => a.id))}>Dismiss all</button>}
          </div>
          {alerts.error && <p className="pad small muted m0">{alerts.error}</p>}
          {active.length === 0 && !alerts.error && <p className="pad muted m0">Nothing needs your attention right now.</p>}
          <ul>
            {active.slice(0, 12).map((a) => (
              <li key={a.id} className={`alert-item a-${a.level}`}>
                <button className="alert-main" onClick={() => openAlert(a)}>
                  <span className="alert-title">{a.title}</span>
                  <span className="small muted">{a.detail}</span>
                  <span className="small muted">{timeAgo(a.time)}</span>
                </button>
                <button className="icon-btn" onClick={() => dismissedAlerts.toggle(a.id)} aria-label="Dismiss alert">×</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SearchPalette({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState('');
  const [res, setRes] = useState<SearchResult | null>(null);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    if (!q.trim()) {
      setRes(null);
      return;
    }
    const t = setTimeout(() => {
      api.search(q).then((r) => {
        setRes(r);
        setActive(0);
      }).catch(() => setRes({ regions: [], satellites: [] }));
    }, 150);
    return () => clearTimeout(t);
  }, [q]);

  const pages = PAGES.filter((p) => q && p.label.toLowerCase().startsWith(q.toLowerCase()));
  const items = [
    ...pages.map((p) => ({ key: `p-${p.id}`, label: p.label, sub: 'Page', go: () => go(p.id) })),
    ...(res?.regions ?? []).map((r) => ({ key: `r-${r.id}`, label: r.name, sub: 'Region', go: () => go('overview', r.id) })),
    ...(res?.satellites ?? []).map((s) => ({ key: `s-${s.norad_id}`, label: s.name, sub: `${s.category_label}, NORAD ${s.norad_id}`, go: () => go('satellites', s.norad_id) })),
  ];

  const choose = (i: number) => {
    const it = items[i];
    if (!it) return;
    it.go();
    onClose();
  };

  return (
    <div className="modal-bg" onMouseDown={onClose}>
      <div className="palette" role="dialog" aria-label="Search" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <SearchIcon />
          <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search regions, satellites or pages"
            aria-label="Search" onKeyDown={(e) => {
              if (e.key === 'Escape') onClose();
              else if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
              else if (e.key === 'Enter') choose(active);
            }} />
          <span className="kbd">Esc</span>
        </div>
        <ul className="palette-list" role="listbox">
          {items.map((it, i) => (
            <li key={it.key} role="option" aria-selected={i === active}>
              <button className={i === active ? 'on' : ''} onMouseEnter={() => setActive(i)} onClick={() => choose(i)}>
                <span>{it.label}</span><span className="small muted">{it.sub}</span>
              </button>
            </li>
          ))}
          {q && res && items.length === 0 && <li className="pad muted">No regions or satellites match “{q}”.</li>}
          {!q && <li className="pad muted small">Type a region name like “Red Sea”, a satellite like “ISS”, or a NORAD number.</li>}
        </ul>
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <circle cx="6" cy="6" r="4.5" fill="none" stroke="#8C8C88" strokeWidth="1.4" />
      <path d="M9.5 9.5l3 3" stroke="#8C8C88" strokeWidth="1.4" />
    </svg>
  );
}
