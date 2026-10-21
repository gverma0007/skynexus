import { useEffect, useState } from 'react';

export type Page = 'overview' | 'regions' | 'satellites' | 'events' | 'reports' | 'system';
export const PAGES: { id: Page; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'regions', label: 'Regions' },
  { id: 'satellites', label: 'Satellites' },
  { id: 'events', label: 'Events' },
  { id: 'reports', label: 'Reports' },
  { id: 'system', label: 'System' },
];

export interface Route {
  page: Page;
  id: string | null;
  params: URLSearchParams;
}

function parse(): Route {
  const raw = window.location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const [page, id] = path.split('/');
  const valid = PAGES.some((p) => p.id === page);
  return { page: valid ? (page as Page) : 'overview', id: id || null, params: new URLSearchParams(query) };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => setRoute(parse());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
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
