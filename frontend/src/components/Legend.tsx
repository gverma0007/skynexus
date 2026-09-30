import React from 'react';
import { SAT_CATEGORIES } from '../lib/satellites';
import type { SatCategory } from '../lib/satellites';

interface LegendProps {
  /** Counts per category, e.g. from /api/ingest/status. */
  satCounts?: Record<string, number>;
  /** Categories currently hidden. */
  hidden: Set<SatCategory>;
  onToggle: (cat: SatCategory) => void;
}

const Legend: React.FC<LegendProps> = ({ satCounts, hidden, onToggle }) => {
  const severityItems: { color: string; label: string }[] = [
    { color: 'bg-rose-500', label: 'High (≥70)' },
    { color: 'bg-amber-400', label: 'Medium (≥40)' },
    { color: 'bg-sky-400', label: 'Low (≥20)' },
    { color: 'bg-emerald-500', label: 'Normal' },
  ];

  const cats = Object.entries(SAT_CATEGORIES) as [
    SatCategory,
    (typeof SAT_CATEGORIES)[SatCategory],
  ][];

  return (
    <div className="absolute bottom-3 right-3 z-20 rounded-lg border border-slate-700/60 bg-slate-900/85 p-3 text-[10px] backdrop-blur">
      <div className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-500">
        Disruption
      </div>
      <div className="space-y-1">
        {severityItems.map((it) => (
          <div key={it.label} className="flex items-center gap-2 text-slate-300">
            <span className={`h-2 w-2 rounded-full ${it.color}`} />
            {it.label}
          </div>
        ))}
      </div>

      <div className="mt-2 border-t border-slate-700/60 pt-2">
        <div className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-500">
          Satellites <span className="text-slate-600">(click to toggle)</span>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {cats.map(([key, meta]) => {
            const count = satCounts?.[key] ?? 0;
            const isHidden = hidden.has(key);
            return (
              <button
                key={key}
                onClick={() => onToggle(key)}
                title={`${meta.label} — ${count} tracked`}
                className={`flex items-center gap-1.5 text-left transition-opacity ${
                  isHidden ? 'opacity-30' : 'hover:opacity-80'
                }`}
              >
                <span className={`h-2 w-2 rotate-45 ${meta.tailwind}`} />
                <span className="text-slate-300">{meta.label.split(' ')[0]}</span>
                <span className="text-slate-600">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-2 space-y-1 border-t border-slate-700/60 pt-2 text-slate-400">
        <div className="flex items-center gap-2">
          <span className="inline-block h-px w-4 bg-sky-400" />
          Flight arc
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-100">▲</span>
          Aircraft
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-rose-400" />
          Event
        </div>
      </div>
    </div>
  );
};

export default Legend;
