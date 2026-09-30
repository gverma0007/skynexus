import React from 'react';
import type { RegionDisruption } from '../api/client';

interface RegionalAnomalyListProps {
  disruptions: RegionDisruption[];
  selectedRegionId: string | null;
  onSelect: (regionId: string | null) => void;
}

const severityStyle = (label: string): string => {
  switch (label) {
    case 'high':
      return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    case 'medium':
      return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    case 'low':
      return 'bg-sky-500/20 text-sky-300 border-sky-500/40';
    default:
      return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
  }
};

const RegionalAnomalyList: React.FC<RegionalAnomalyListProps> = ({
  disruptions,
  selectedRegionId,
  onSelect,
}) => {
  const sorted = [...disruptions].sort((a, b) => b.composite_index - a.composite_index);

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-slate-400">
        Regional Disruption Index
      </h2>
      {sorted.length === 0 ? (
        <p className="text-sm text-slate-500">No regions loaded.</p>
      ) : (
        <ul className="space-y-2 overflow-y-auto pr-1">
          {sorted.map((d) => (
            <li key={d.region_id}>
              <button
                onClick={() => onSelect(selectedRegionId === d.region_id ? null : d.region_id)}
                className={`w-full rounded-lg border p-2.5 text-left transition-colors ${
                  selectedRegionId === d.region_id
                    ? 'border-sky-400/60 bg-sky-500/10'
                    : 'border-slate-700/50 bg-slate-800/40 hover:border-slate-600 hover:bg-slate-800/70'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-slate-100">{d.region_name}</span>
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${severityStyle(
                      d.severity_label
                    )}`}
                  >
                    {d.composite_index.toFixed(0)}
                  </span>
                </div>
                <div className="mt-1.5 flex gap-1">
                  <div
                    className="h-1 rounded-full bg-sky-400/70"
                    style={{ width: `${d.flight_anomaly_score}%` }}
                    title={`Flight anomaly ${d.flight_anomaly_score}`}
                  />
                  <div
                    className="h-1 rounded-full bg-amber-400/70"
                    style={{ width: `${d.event_relevance_score}%` }}
                    title={`Events ${d.event_relevance_score}`}
                  />
                  <div
                    className="h-1 rounded-full bg-rose-400/70"
                    style={{ width: `${d.weather_score}%` }}
                    title={`Weather ${d.weather_score}`}
                  />
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default RegionalAnomalyList;
