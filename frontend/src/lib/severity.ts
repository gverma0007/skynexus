// Severity bands shared by every component. Defaults match the backend
// Settings (SEVERITY_LOW/MEDIUM/HIGH env vars) and are refreshed from the
// /api/stats payload so both sides always agree.

export interface SeverityBands {
  low: number;
  medium: number;
  high: number;
}

export const DEFAULT_BANDS: SeverityBands = { low: 20, medium: 40, high: 70 };

let bands: SeverityBands = { ...DEFAULT_BANDS };

export function applyBands(next: Partial<SeverityBands> | undefined): void {
  if (!next) return;
  bands = {
    low: Number(next.low) || DEFAULT_BANDS.low,
    medium: Number(next.medium) || DEFAULT_BANDS.medium,
    high: Number(next.high) || DEFAULT_BANDS.high,
  };
}

export function getBands(): SeverityBands {
  return { ...bands };
}

export type Severity = 'normal' | 'low' | 'medium' | 'high';

export function severityOf(score: number): Severity {
  if (score >= bands.high) return 'high';
  if (score >= bands.medium) return 'medium';
  if (score >= bands.low) return 'low';
  return 'normal';
}

/** Tailwind class fragments per severity, usable for bg/text/border. */
export const SEVERITY_TEXT: Record<Severity, string> = {
  normal: 'text-emerald-400',
  low: 'text-sky-400',
  medium: 'text-amber-400',
  high: 'text-rose-400',
};

export const SEVERITY_BG: Record<Severity, string> = {
  normal: 'bg-emerald-500',
  low: 'bg-sky-400',
  medium: 'bg-amber-400',
  high: 'bg-rose-500',
};

/** Globe-side hex colors (three.js needs numbers, not classes). */
export const SEVERITY_HEX: Record<Severity, number> = {
  normal: 0x22c55e,
  low: 0x38bdf8,
  medium: 0xfbbf24,
  high: 0xf43f5e,
};
