import React from 'react';
import type { StatsSummary } from '../api/client';
import { SEVERITY_TEXT, severityOf } from '../lib/severity';

interface TopStatBarProps {
  stats: StatsSummary | null;
}

const Stat: React.FC<{ label: string; value: string | number; accent?: string }> = ({
  label,
  value,
  accent,
}) => (
  <div className="flex flex-col">
    <span className="text-[10px] uppercase tracking-widest text-sky-400/70">{label}</span>
    <span className={`text-lg font-bold leading-tight ${accent ?? 'text-slate-100'}`}>{value}</span>
  </div>
);

export const TopStatBar: React.FC<TopStatBarProps> = ({ stats }) => {
  if (!stats) {
    return (
      <div className="absolute top-4 left-4 right-4 z-20 rounded-lg border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
        <div className="h-6 w-full animate-pulse rounded bg-slate-700/60" />
      </div>
      );
  }
  const idx = stats.global_disruption_index;
  const idxColor = SEVERITY_TEXT[severityOf(idx)];

  return (
    <div className="absolute top-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 rounded-lg border border-slate-700/60 bg-slate-900/80 px-5 py-3 backdrop-blur">
      <Stat label="Flights 24h" value={stats.flights_24h.toLocaleString()} />
      <Stat label="Satellites" value={stats.satellites_tracked} />
      <Stat label="Active Events" value={stats.active_events} accent="text-amber-400" />
      <Stat label="Regions" value={stats.regions_monitored} />
      <div className="ml-auto flex items-center gap-3">
        <Stat
          label="Most disrupted"
          value={stats.most_disrupted_region ?? '—'}
          accent="text-rose-400"
        />
        <div className="h-8 w-px bg-slate-700" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest text-sky-400/70">Global Index</span>
          <span className={`text-2xl font-black ${idxColor}`}>{idx.toFixed(1)}</span>
        </div>
      </div>
   </div>
  );
};
