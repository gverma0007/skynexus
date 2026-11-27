import { useEffect, useRef, useState } from 'react';
import { api, BASE, clearApiCache, request } from './lib/api';
import { usePoll } from './lib/usePoll';
import { go, href, PAGES, useRoute } from './lib/router';
import type { Page } from './lib/router';
import { useViewer, viewer } from './lib/viewer';
import { useActivity } from './lib/activity';
import Icon from './components/Icon';
import Globe from './globe/Globe';
import Overview from './pages/Overview';
import Regions from './pages/Regions';
import Satellites from './pages/Satellites';
import Events from './pages/Events';
import Reports from './pages/Reports';
import System from './pages/System';
import { Sources, Incidents, DomainSignals, Forecasts, Replay, Experiments, Exposures, Methodology } from './pages/Research';

type User = { email: string; role?: string };
export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [expired, setExpired] = useState(false);
  const [directDemo, setDirectDemo] = useState(false);
  const [bootError, setBootError] = useState('');
  useEffect(() => {
    const onPath = () => setPath(window.location.pathname);
    const unauthorized = () => { setUser(null); setExpired(true); navigate('/login'); };
    window.addEventListener('popstate', onPath);
    window.addEventListener('skynexus:navigate', onPath);
    window.addEventListener('skynexus:unauthorized', unauthorized);
    let alive = true;
    const boot = async () => {
      for (let attempt = 0; attempt < 5 && alive; attempt++) {
        try {
          const options = await api.authOptions();
          if (!alive) return;
          viewer.configure(options.capabilities?.profile ?? 'full');
          setDirectDemo(options.direct_demo_login);
          const account = await api.me().catch(() => null);
          if (!alive) return;
          setUser(account); setChecking(false); return;
        } catch {
          if (attempt < 4) await new Promise((resolve) => setTimeout(resolve, 3000));
        }
      }
      if (alive) { setBootError('SkyNexus is waking up or temporarily unavailable. Please try again shortly.'); setChecking(false); }
    };
    void boot();
    return () => { alive = false; window.removeEventListener('popstate', onPath); window.removeEventListener('skynexus:navigate', onPath); window.removeEventListener('skynexus:unauthorized', unauthorized); };
  }, []);
  const inApp = path === '/app' || path.startsWith('/app/') || window.location.hash.startsWith('#/');
  if (path === '/methodology') return <div className="public-page"><PublicHeader /><Methodology /><PublicFooter /></div>;
  const openWorkspace = (u: User) => { clearApiCache(); setUser(u); setExpired(false); navigate('/app'); if (viewer.get().profile === 'free_demo') go('replay'); };
  if (bootError) return <div className="boot"><Logo /><p role="alert">{bootError}</p><button className="btn primary" onClick={() => window.location.reload()}>Retry opening SkyNexus</button></div>;
  if (path === '/login' || (inApp && !user && !checking)) return <Login directDemo={directDemo} expired={expired} onLogin={openWorkspace} />;
  if (!inApp) return <Landing directDemo={directDemo} onLogin={openWorkspace} />;
  if (checking) return <div className="boot"><Logo /><span>Opening your workspace… A sleeping demo may take about a minute to wake up.</span></div>;
  return user ? <Workspace user={user} onLogout={async () => { await api.logout(); clearApiCache(); setUser(null); navigate('/'); }} /> : null;
}

function navigate(path: string) { window.history.pushState(null, '', path); window.dispatchEvent(new Event('skynexus:navigate')); }
function Logo() { return <span className="wordmark"><span className="logo-mark"><Icon name="globe" size={23} /></span>SkyNexus<span className="wordmark-dot">.</span></span>; }
function PublicHeader() { return <header className="public-header"><a href="/" className="logo-link"><Logo /></a><nav><a href="/methodology">Methodology</a><a href="/login" className="btn primary">Open workspace <Icon name="arrow" size={15} /></a></nav></header>; }
function PublicFooter() { return <footer className="public-footer"><Logo /><span>Open data. Explainable signals. Evidence before conclusions.</span><span>Research prototype</span></footer>; }
function DemoEntry({ onLogin, large = false }: { onLogin: (user: User) => void; large?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <div className="demo-entry"><button className={`btn primary ${large ? 'large' : ''}`} disabled={busy} onClick={async () => { if (busy) return; setBusy(true); setError(''); try { onLogin(await api.enterDemo()); } catch (err) { setError(err instanceof Error ? err.message : 'Could not open the demo. Please retry.'); } finally { setBusy(false); } }}>{busy ? 'Opening demo…' : 'Enter demo'}<Icon name="arrow" size={17} /></button>{error && <p className="login-error" role="alert">{error}</p>}</div>;
}
function Landing({ directDemo, onLogin }: { directDemo: boolean; onLogin: (user: User) => void }) {
  return <div className="landing"><PublicHeader /><main>
    <section className="hero"><div className="hero-copy"><div className="research-tag"><span />A connected view of a changing world</div>
      <h1>See the change.<br />Understand the impact.</h1><p>Explore activity across the sky, sea and ground. Investigate unusual patterns, connect the evidence, and understand what might happen next.</p>
      <div className="hero-actions">{directDemo ? <DemoEntry onLogin={onLogin} large /> : <a className="btn primary large" href="/login">Explore SkyNexus <Icon name="arrow" /></a>}<a href="/methodology" className="text-link">How the research works <Icon name="chevron" size={15} /></a></div>
      <div className="hero-note"><Icon name="shield" size={16} /><span>Public sources. Transparent methods. No unsupported claims.</span></div></div>
      <div className="hero-globe"><Globe regions={[]} flights={[]} sats={[]} events={[]} layers={{ aircraft: false, satellites: false, events: false, outlines: false }} selectedRegion={null} selectedSat={null} focus={null} onSelectRegion={() => {}} onSelectSat={() => {}} compact />
        <div className="hero-map-caption"><span className="pulse-dot" /><div><strong>One planet. Connected systems.</strong><span>Reference imagery · Explore the evidence inside</span></div></div></div>
    </section>
    <section className="domain-band"><span>Explore connected signals</span>{['Aviation', 'Maritime', 'Environment', 'Infrastructure', 'Space'].map((name) => <span key={name}><Icon name={name === 'Environment' ? 'layers' : name === 'Infrastructure' ? 'signals' : 'globe'} size={17} />{name}</span>)}</section>
    <section className="landing-story"><div><p className="section-kicker">From observation to understanding</p><h2>A signal matters more<br />when you can explain it.</h2></div><div className="story-steps">
      <div><span>01</span><section><h3>Establish what is normal</h3><p>Compare activity with its own history, including data coverage and seasonal patterns.</p></section></div>
      <div><span>02</span><section><h3>Investigate what changed</h3><p>Inspect observations, weather and documented events together. Keep alternative explanations visible.</p></section></div>
      <div><span>03</span><section><h3>Follow the evidence forward</h3><p>Explore defined forecast targets and reproducible reports, with uncertainty and limitations included.</p></section></div>
    </div></section>
    <section className="landing-final"><div><h2>Make your next investigation a connected one.</h2><p>A research workspace for regional disruption, anomaly detection and pattern analysis.</p></div>{directDemo ? <DemoEntry onLogin={onLogin} large /> : <a className="btn primary large" href="/login">Open workspace <Icon name="arrow" /></a>}</section>
  </main><PublicFooter /></div>;
}

function Login({ onLogin, expired, directDemo }: { onLogin: (user: User) => void; expired: boolean; directDemo: boolean }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <div className="login-page"><a className="login-brand logo-link" href="/"><Logo /></a><div className="login-layout">
    <section className="login-story"><div className="research-tag"><span />The regional intelligence workspace</div><h1>The world changes.<br />Find the signals<br />that matter.</h1><p>Bring observations into context. Trace every finding back to its evidence.</p><div className="login-orbit" aria-hidden="true"><i /><i /><i /><span><Icon name="globe" size={96} /></span></div><span className="login-footnote">Built for exploration. Grounded in public data.</span></section>
    <section className="login-card"><span className="tiny-label">Welcome to SkyNexus</span><h2>Open your workspace</h2><p>{directDemo ? 'Explore the research demo, or sign in with your provisioned account.' : 'Sign in with your provisioned demo account.'}</p>
      {expired && <div className="context-notice">Your session ended. Sign in again to continue.</div>}
      {directDemo && <div className="direct-demo-option"><DemoEntry onLogin={onLogin} large /><p>No password needed for this demonstration.</p><span>Or sign in with email</span></div>}
      <form onSubmit={async (e) => { e.preventDefault(); if (busy) return; setBusy(true); setError(''); try { await api.login(email.trim(), password); onLogin(await api.me()); } catch (err) { setError(err instanceof Error ? err.message : 'Sign in failed. Please try again.'); } finally { setBusy(false); } }}>
        <label className="login-field">Email address<input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required disabled={busy} /></label>
        <label className="login-field">Password<span className="password-wrap"><input type={visible ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" required disabled={busy} /><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? 'Hide password' : 'Show password'}><Icon name="eye" /></button></span></label>
        {error && <p className="login-error" role="alert">{error}</p>}
        <button type="submit" className="btn primary large login-submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<Icon name="arrow" /></button>
      </form><p className="account-note"><Icon name="shield" size={17} />{directDemo ? 'Demo access opens a server-side session. Saved reports and downloads belong to that session.' : 'A research demo with secure, server-side sign in. Contact the project administrator for access.'}</p><a className="back-link" href="/">Back to SkyNexus</a></section>
  </div></div>;
}

const NAV: { label: string; items: { id: Page; label: string; icon: string }[] }[] = [
  { label: 'Monitor', items: [{ id: 'overview', label: 'Dashboard', icon: 'dashboard' }, { id: 'explore', label: 'Explore', icon: 'explore' }, { id: 'incidents', label: 'Incidents', icon: 'incidents' }, { id: 'regions', label: 'Regions', icon: 'regions' }] },
  { label: 'Analyse', items: [{ id: 'forecasts', label: 'Forecasts', icon: 'forecasts' }, { id: 'replay', label: 'Historical replay', icon: 'replay' }, { id: 'experiments', label: 'Experiments', icon: 'experiments' }, { id: 'reports', label: 'Reports', icon: 'reports' }] },
  { label: 'Data', items: [{ id: 'signals', label: 'Domain signals', icon: 'signals' }, { id: 'exposures', label: 'Infrastructure exposure', icon: 'layers' }, { id: 'satellites', label: 'Space catalogue', icon: 'globe' }, { id: 'sources', label: 'Sources', icon: 'sources' }] },
];
function Workspace({ user, onLogout }: { user: User; onLogout: () => Promise<void> }) {
  const route = useRoute();
  const state = useViewer();
  const freeDemo = state.profile === 'free_demo';
  const active = useActivity(freeDemo);
  const regions = usePoll(api.regions, 60_000);
  const outlines = usePoll(api.outlines, 0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  useEffect(() => {
    const breakpoint = window.matchMedia('(max-width: 760px)');
    const closeOnResize = () => setMobileNav(false);
    breakpoint.addEventListener('change', closeOnResize);
    return () => breakpoint.removeEventListener('change', closeOnResize);
  }, []);
  const current = NAV.flatMap((group) => group.items).find((item) => item.id === route.page);
  useEffect(() => { document.title = `${current?.label ?? 'SkyNexus'} · SkyNexus`; setMobileNav(false); }, [route.page, current?.label]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setSearchOpen((open) => !open); } if (e.key === 'Escape') { setSearchOpen(false); setMobileNav(false); } };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);
  useEffect(() => {
    if (!state.realtime || state.dataset === 'historical' || !active || freeDemo) return;
    let alive = true;
    let stream: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const connect = async () => {
      try {
        const snapshot = await request<{ watermark: number }>('/snapshot');
        if (!alive) return;
        stream = new EventSource(`${BASE}/stream?data_mode=${state.dataset}&cursor=${snapshot.watermark}`, { withCredentials: true });
        stream.onopen = () => viewer.connection('receiving');
        stream.addEventListener('update', () => viewer.received());
        stream.addEventListener('session_expired', () => window.dispatchEvent(new Event('skynexus:unauthorized')));
        stream.onerror = () => viewer.connection('reconnecting');
      } catch {
        if (alive) { viewer.connection('reconnecting'); retry = setTimeout(connect, 5000); }
      }
    };
    void connect();
    return () => { alive = false; stream?.close(); if (retry) clearTimeout(retry); };
  }, [state.realtime, state.dataset, active, freeDemo]);
  let body;
  switch (route.page) {
    case 'regions': body = <Regions regions={regions.data} error={regions.error} />; break;
    case 'satellites': body = <Satellites selected={route.id ? Number(route.id) : null} />; break;
    case 'events': body = <Events regions={regions.data} outlines={outlines.data} tab={route.id === 'anomalies' ? 'anomalies' : 'quakes'} />; break;
    case 'reports': body = <Reports regions={regions.data} reportId={route.id} params={route.params} />; break;
    case 'sources': body = <Sources selected={route.id} />; break;
    case 'incidents': body = <Incidents />; break;
    case 'signals': body = <DomainSignals domain={route.id ?? 'environment'} />; break;
    case 'forecasts': body = <Forecasts regions={regions.data} />; break;
    case 'replay': body = <Replay regions={regions.data} />; break;
    case 'experiments': body = <Experiments />; break;
    case 'exposures': body = <Exposures />; break;
    case 'methodology': body = <Methodology />; break;
    case 'system': body = <System />; break;
    default: body = <Overview regions={regions.data} regionsError={regions.error} outlines={outlines.data} selectedId={route.id} explore={route.page === 'explore'} />;
  }
  return <div className={`workspace ${mobileNav ? 'nav-open' : ''}`}><a className="skip" href="#main">Skip to content</a>
    {mobileNav && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <aside className="sidebar"><a href="/" className="sidebar-brand logo-link"><Logo /></a><div className="workspace-label"><span className="workspace-emblem"><Icon name="layers" size={18} /></span><div><b>Research workspace</b><span>Regional intelligence</span></div><Icon name="chevron" size={14} /></div><button className="sidebar-search" onClick={() => setSearchOpen(true)}><Icon name="search" size={17} />Search anything<kbd>⌘ K</kbd></button>
      <nav aria-label="Main navigation">{NAV.map((group) => <div className="nav-group" key={group.label}><span>{group.label}</span>{group.items.map((item) => <a key={item.id} href={href(item.id)} className={route.page === item.id ? 'selected' : ''} aria-current={route.page === item.id ? 'page' : undefined}><Icon name={item.icon} />{item.label}{item.id === 'explore' && <span className="nav-new">4 views</span>}</a>)}</div>)}</nav>
      <div className="sidebar-bottom"><a href={href('methodology')}><Icon name="book" />Methodology</a><button onClick={() => onLogout().catch(() => setLogoutError('Could not sign out. Please retry.'))}><Icon name="logout" />Sign out</button>{logoutError && <span className="login-error">{logoutError}</span>}<div className="account"><span className="avatar">{user.email[0]?.toUpperCase() ?? 'D'}</span><div><b>Demo researcher</b><span>{user.email}</span></div><span className="account-dot" /></div></div>
    </aside>
    <div className="workspace-content"><header className="workspace-header"><button className="mobile-menu" aria-label={mobileNav ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileNav} onClick={() => setMobileNav(!mobileNav)}><Icon name="menu" /></button><div className="breadcrumbs"><Icon name={current?.icon ?? 'globe'} size={17} /><span>Workspace</span><span>/</span><b>{current?.label ?? PAGES.find((p) => p.id === route.page)?.label ?? 'Dashboard'}</b></div><div className={`connection connection-${state.connection}`}><span />{!active ? 'View idle' : freeDemo ? 'Replay ready' : state.connection === 'receiving' ? 'Connected' : state.connection === 'paused' ? 'View paused' : state.connection === 'connecting' ? 'Connecting' : 'Reconnecting'}</div><span className="avatar small-avatar">{user.email[0]?.toUpperCase() ?? 'D'}</span></header>
      <div className="context-bar"><div className="context-scope"><Icon name="globe" size={16} /><span>Global overview</span><span className="context-divider" />Selected regions in depth</div><div className="context-controls"><label className="dataset-control"><span className={`dataset-dot ${state.dataset}`} /><select aria-label="Dataset" value={state.dataset} onChange={(e) => { if (e.target.value === 'historical') go('replay'); else { clearApiCache(); viewer.setDataset(e.target.value as 'live' | 'demo'); } }}><option value="live">{freeDemo ? 'Stored sources' : 'Live sources'}</option><option value="demo">Synthetic scenario</option><option value="historical">Historical replay</option></select></label><button className={`realtime-toggle ${state.realtime ? 'enabled' : ''}`} disabled={state.dataset === 'historical' || freeDemo} title={freeDemo ? 'Continuous collection is available in the full workspace' : undefined} onClick={() => state.realtime ? viewer.pause() : viewer.resume()} aria-pressed={state.realtime}><span className="toggle-track"><i /></span>Realtime</button></div></div>
      {state.dataset === 'demo' && <div className="mode-banner synthetic"><Icon name="experiments" size={16} /><span>Synthetic scenario. Generated observations are for demonstration and are separate from live evidence.</span></div>}
      {freeDemo && <div className="mode-banner"><Icon name="replay" size={16} /><span>Sleeping research demo · Eight real historical studies and cached evaluations. Continuous collection is paused.</span><button onClick={() => { clearApiCache(); viewer.refresh(); }}>Refresh view</button></div>}
      {!state.realtime && !freeDemo && <div className="mode-banner"><Icon name="pause" size={16} /><span>{state.dataset === 'historical' ? 'Historical view' : 'Your view is paused'}{state.asOf ? ` at ${new Date(state.asOf).toLocaleString()}` : ''}. Source collection continues.</span><button onClick={() => { clearApiCache(); viewer.setDataset('live'); }}>Return to latest <Icon name="arrow" size={14} /></button></div>}
      <main id="main" className="workspace-main">{body}</main><footer className="workspace-footer"><span>SkyNexus Research</span><span>Statistical change and association. Correlation does not establish causation.</span></footer>
    </div>{searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} />}</div>;
}
function SearchDialog({ onClose }: { onClose: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => { const prior = document.activeElement; input.current?.focus(); return () => { if (prior instanceof HTMLElement) prior.focus(); }; }, []);
  useEffect(() => { let alive = true; const timeout = setTimeout(() => { if (!query.trim()) return setMatches([]); api.search(query).then((r) => { if (alive) setMatches(r.regions); }).catch(() => setMatches([])); }, 200); return () => { alive = false; clearTimeout(timeout); }; }, [query]);
  const pages = PAGES.filter((page) => page.label.toLowerCase().includes(query.toLowerCase()));
  return <div className="modal-bg" onClick={onClose}><section role="dialog" aria-modal="true" aria-label="Search workspace" className="palette" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === 'Tab') { const elements = e.currentTarget.querySelectorAll<HTMLElement>('input, button, a'); const first = elements[0], last = elements[elements.length - 1]; if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } } }}><div className="palette-input"><Icon name="search" /><input ref={input} aria-label="Search" placeholder="Search pages and regions…" value={query} onChange={(e) => setQuery(e.target.value)} /><button className="icon-btn" aria-label="Close search" onClick={onClose}>×</button></div><div className="search-results">{pages.slice(0, 9).map((page) => <button key={page.id} onClick={() => { go(page.id); onClose(); }}><Icon name="chevron" size={16} />{page.label}<span>Page</span></button>)}{matches.map((region) => <button key={region.id} onClick={() => { go('explore', region.id); onClose(); }}><Icon name="regions" size={16} />{region.name}<span>Region</span></button>)}{!pages.length && !matches.length && <p className="pad muted">No results. Try a page name or monitored region.</p>}</div></section></div>;
}
