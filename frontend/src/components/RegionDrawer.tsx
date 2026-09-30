import React from 'react';
import { SEVERITY_TEXT, severityOf } from '../lib/severity';
import type { RegionDisruption, RegionMapPoint } from '../api/client';

interface RegionDrawerProps {
  region: RegionMapPoint | null;
  disruption: RegionDisruption | null;
  onClose: () => void;
  onWhatChanged: () => void;
}

const Breakdown: React.FC<{ label: string; value: number; color: string }> = ({
  label,
  value,
  color,
}) => (
  <div>
    <div className="mb-1 flex items-center justify-between text-xs">
      <span className="text-slate-400">{label}</span>
      <span className={`font-bold ${color}`}>{value.toFixed(0)}</span>
    </div>
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700/60">
      <div
        className={`h-full rounded-full ${color.replace('text-', 'bg-')}`}
        style={{ width: `${Math.max(2, Math.min(100, value))}%` }}
      />
    </div>
  </div>
);

const RegionDrawer: React.FC<RegionDrawerProps> = ({
  region,
  disruption,
  onClose,
  onWhatChanged,
}) => {
  if (!region) return null;
  const flight = disruption?.flight_anomaly_score ?? region.flight_anomaly_score;
  const events = disruption?.event_relevance_score ?? region.event_relevance_score;
  const weather = disruption?.weather_score ?? region.weather_score;
  const composite = disruption?.composite_index ?? region.composite_index;

  return (
    <div className="absolute right-3 top-3 z-30 w-72 rounded-xl border border-sky-500/30 bg-slate-900/95 p-4 shadow-2xl backdrop-blur">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-sky-400/80">
            Region Detail
          </div>
          <h3 className="text-lg font-black text-slate-100">{region.name}</h3>
        </div>
        <button
          onClick={onClose}
          className="rounded px-1.5 text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-200"
        >
          ✕
        </button>
      </div>

      <div className="my-3 flex items-baseline gap-2">
        <span className={`text-4xl font-black ${SEVERITY_TEXT[severityOf(composite)]}`}>
          {composite.toFixed(1)}
        </span>
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
          {severityOf(composite)}
        </span>
      </div>

      <div className="space-y-3">
        <Breakdown label="Flight anomaly" value={flight} color="text-sky-400" />
        <Breakdown label="Event relevance" value={events} color="text-amber-400" />
        <Breakdown label="Weather / storm" value={weather} color="text-rose-400" />
      </div>

      <button
        onClick={onWhatChanged}
        className="mt-4 w-full rounded-lg bg-sky-500 py-2 text-xs font-bold text-slate-950 transition-colors hover:bg-sky-400"
      >
        What Changed here? →
      </button>
    </div>
  );
};

export default RegionDrawer;
