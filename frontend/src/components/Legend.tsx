import React from 'react';

const Legend: React.FC = () => {
  const items: { color: string; label: string }[] = [
    { color: 'bg-rose-500', label: 'High (≥75)' },
    { color: 'bg-amber-400', label: 'Medium (≥50)' },
    { color: 'bg-sky-400', label: 'Low (≥25)' },
    { color: 'bg-emerald-500', label: 'Normal' },
  ];
  return (
    <div className="absolute bottom-3 right-3 z-20 rounded-lg border border-slate-700/60 bg-slate-900/85 p-3 backdrop-blur">
      <div className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-500">
        Disruption
      </div>
      <div className="space-y-1">
        {items.map((it) => (
          <div key={it.label} className="flex items-center gap-2 text-[10px] text-slate-300">
            <span className={`h-2 w-2 rounded-full ${it.color}`} />
            {it.label}
          </div>
        ))}
      </div>
      <div className="mt-2 space-y-1 border-t border-slate-700/60 pt-2 text-[10px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="inline-block h-px w-4 bg-sky-400" />
          Flight arc
        </div>
        <div className="flex items-center gap-2">
          <span className="text-amber-400">◆</span>
          Satellite
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
