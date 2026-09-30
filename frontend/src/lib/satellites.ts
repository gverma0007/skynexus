// Satellite functional categories with globe colors and display metadata.

export type SatCategory =
  | 'station'
  | 'weather'
  | 'science'
  | 'nav'
  | 'earthobs'
  | 'comms'
  | 'other';

export const SAT_CATEGORIES: Record<
  SatCategory,
  { label: string; hex: number; tailwind: string }
> = {
  station: { label: 'Crewed station', hex: 0xf472b6, tailwind: 'bg-pink-400' },
  weather: { label: 'Weather', hex: 0x38bdf8, tailwind: 'bg-sky-400' },
  science: { label: 'Science', hex: 0xa78bfa, tailwind: 'bg-violet-400' },
  nav: { label: 'Navigation', hex: 0x34d399, tailwind: 'bg-emerald-400' },
  earthobs: { label: 'Earth observation', hex: 0xfbbf24, tailwind: 'bg-amber-400' },
  comms: { label: 'Communications', hex: 0xfb923c, tailwind: 'bg-orange-400' },
  other: { label: 'Other', hex: 0x94a3b8, tailwind: 'bg-slate-400' },
};

export function satCategoryOf(raw: string | undefined): SatCategory {
  const key = (raw ?? 'other') as SatCategory;
  return key in SAT_CATEGORIES ? key : 'other';
}
