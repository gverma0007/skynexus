import type { Severity, Status } from './api';

export const STATUS_LEVEL: Record<Status, 0 | 1 | 2 | 3> = { Calm: 0, Watch: 1, Elevated: 2, Critical: 3 };
export const SEVERITY_LEVEL: Record<Severity, 0 | 1 | 2 | 3> = { normal: 0, low: 1, medium: 2, high: 3 };

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never';
  const s = Math.round((now - new Date(iso).getTime()) / 1000);
  if (s < 0) return `in ${fmtDuration(-s)}`;
  if (s < 45) return 'just now';
  return `${fmtDuration(s)} ago`;
}

export function fmtDuration(s: number): string {
  if (s < 90) return `${Math.max(1, Math.round(s / 60))} min`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  if (s < 86400) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} d`;
}

export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  return v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '–';
  const r = Math.round(v);
  return `${r > 0 ? '+' : ''}${r}%`;
}

export function fmtChange(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'no comparison yet';
  const r = Math.round(v);
  if (r === 0) return 'unchanged from yesterday';
  return `${r > 0 ? 'up' : 'down'} ${Math.abs(r)} from yesterday`;
}

export function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}
