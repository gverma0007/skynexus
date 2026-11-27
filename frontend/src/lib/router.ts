import { useEffect, useState } from 'react';

export type Page = 'overview' | 'explore' | 'regions' | 'satellites' | 'events' | 'reports' | 'system' | 'sources' | 'incidents' | 'forecasts' | 'replay' | 'experiments' | 'signals' | 'exposures' | 'methodology';
export const PAGES: { id: Page; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'explore', label: 'Explore' },
  { id: 'incidents', label: 'Incidents' },
  { id: 'regions', label: 'Regions' },
  { id: 'satellites', label: 'Satellites' },
  { id: 'events', label: 'Events' },
  { id: 'reports', label: 'Reports' },
  { id: 'system', label: 'System' },
  { id: 'sources', label: 'Sources' },
  { id: 'forecasts', label: 'Forecasts' },
  { id: 'replay', label: 'Replay' },
  { id: 'experiments', label: 'Experiments' },
  { id: 'signals', label: 'Domain signals' },
  { id: 'exposures', label: 'Infrastructure exposure' },
  { id: 'methodology', label: 'Methodology' },
];

export interface Route {
  page: Page;
  id: string | null;
  params: URLSearchParams;
}

function parse(): Route {
  const raw = window.location.hash.replace(/^#\/?/, '') || window.location.pathname.replace(/^\/app\/?/, '').replace(/^\//, '') + window.location.search;
  const [path, query = ''] = raw.split('?');
  const [rawPage, id] = path.split('/');
  const page = rawPage === 'dashboard' ? 'overview' : rawPage;
  const valid = PAGES.some((p) => p.id === page);
  return { page: valid ? (page as Page) : 'overview', id: id || null, params: new URLSearchParams(query) };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => setRoute(parse());
    window.addEventListener('hashchange', on);
    window.addEventListener('popstate', on);
    return () => { window.removeEventListener('hashchange', on); window.removeEventListener('popstate', on); };
  }, []);
  return route;
}

export function href(page: Page, id?: string | number | null, params?: Record<string, string>): string {
  const qs = params ? `?${new URLSearchParams(params)}` : '';
  return `#/${page}${id != null ? `/${id}` : ''}${qs}`;
}

export function go(page: Page, id?: string | number | null, params?: Record<string, string>) {
  window.location.hash = href(page, id, params);
}
