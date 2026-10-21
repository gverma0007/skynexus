import { useSyncExternalStore } from 'react';

// Small persistent stores (per browser). Storage can be unavailable
// (private mode, blocked site data), so every access is guarded.

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

function createSetStore(key: string) {
  let value = new Set<string>(read<string[]>(key, []));
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());
  return {
    subscribe(l: () => void) {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    get: () => value,
    toggle(id: string) {
      const next = new Set(value);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      value = next;
      write(key, [...next]);
      emit();
    },
    add(ids: string[]) {
      value = new Set([...value, ...ids]);
      write(key, [...value]);
      emit();
    },
  };
}

export const watchlist = createSetStore('skynexus.watchlist');
export const dismissedAlerts = createSetStore('skynexus.dismissedAlerts');

export function useSetStore(store: ReturnType<typeof createSetStore>): Set<string> {
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}
