import { useSyncExternalStore } from 'react';

const listeners = new Set<() => void>();
let visible = document.visibilityState === 'visible';
let active = visible;
let lastInput = Date.now();
let timer: ReturnType<typeof setTimeout> | undefined;
const events = ['pointerdown', 'keydown', 'scroll', 'touchstart'];
function check() {
  const nextVisible = document.visibilityState === 'visible';
  const next = nextVisible && Date.now() - lastInput < 180_000;
  if (next !== active || nextVisible !== visible) { active = next; visible = nextVisible; listeners.forEach((listener) => listener()); }
  if (timer) clearTimeout(timer);
  if (next) timer = setTimeout(check, Math.max(1, 180_000 - (Date.now() - lastInput)));
}
function input() { lastInput = Date.now(); check(); }
function visibility() { if (document.visibilityState === 'visible') lastInput = Date.now(); check(); }
function subscribe(listener: () => void) {
  if (!listeners.size) {
    events.forEach((event) => window.addEventListener(event, input, { passive: true }));
    document.addEventListener('visibilitychange', visibility);
    input();
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (!listeners.size) {
      events.forEach((event) => window.removeEventListener(event, input));
      document.removeEventListener('visibilitychange', visibility);
      if (timer) clearTimeout(timer);
    }
  };
}
export function useActivity(idleTimeout = true) { return useSyncExternalStore(subscribe, () => idleTimeout ? active : visible); }
