import React from 'react';
import { SEVERITY_TEXT, severityOf } from '../lib/severity';
import type { RegionMapPoint } from '../api/client';

export interface PressureZone {
  region_id: string;
  region_name: string;
  lat: number;
  lon: number;
  pressure_index: number;
  classification: 'CALM' | 'WATCH' | 'ELEVATED' | 'CRITICAL';
  description: string;
  drivers: string[];
}

interface PressureZonesProps {
  zones: PressureZone[] | null;
  regions: RegionMapPoint[];
  selectedRegionId: string | null;
  onSelect: (regionId: string | null) => void;
}

const CLASS_STYLE: Record<PressureZone['classification'], string> = {
  CRITICAL: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
  ELEVATED: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  WATCH: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
  CALM: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
};

const PressureZones: React.FC<PressureZonesProps> = ({
  zones,
  regions,
  selectedRegionId,
  onSelect,
}) => {
  if (!zones) {
    return (
      <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 text-xs text-slate-500 backdrop-blur">
        Loading pressure model…
      </div>
    );
  }
  const notable = zones.filter((z) => z.classification !== 'CALM');
  const calmCount = zones.length - notable.length;
  const centroid = new Map(regions.map((r) => [r.id, r]));

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
          Pressure Zones
        </h2>
        <span className="text-[10px] text-slate-600">
          {notable.length} active · {calmCount} calm
        </span>
      </div>
      {notable.length === 0 ? (
        <p className="text-sm text-slate-500">
          All {zones.length} monitored zones are within normal bounds.
        </p>
      ) : (
        <ul className="space-y-2 overflow-y-auto pr-1">
          {notable.map((z) => {
            const isSel = z.region_id === selectedRegionId;
            const pt = centroid.get(z.region_id);
            return (
              <li key={z.region_id}>
                <button
                  onClick={() => onSelect(isSel ? null : z.region_id)}
                  className={`w-full rounded-lg border p-2.5 text-left transition-colors ${
                    isSel
                      ? 'border-sky-400/60 bg-sky-500/10'
                      : 'border-slate-700/50 bg-slate-800/40 hover:border-slate-600 hover:bg-slate-800/70'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-slate-100">
                      {z.region_name}
                    </span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase ${CLASS_STYLE[z.classification]}`}
                    >
                      {z.classification}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-slate-700/60">
                      <div
                        className={`h-full rounded-full ${
                          z.classification === 'CRITICAL'
                            ? 'bg-rose-500'
                            : 'bg-amber-400'
                        }`}
                        style={{ width: `${Math.max(2, z.pressure_index)}%` }}
                      />
                    </div>
                    <span className={`font-mono text-[10px] ${SEVERITY_TEXT[severityOf(z.pressure_index)]}`}>
                      {z.pressure_index.toFixed(0)}
                    </span>
                  </div>
                  {z.drivers.length > 0 && (
                    <div className="mt-1 text-[10px] leading-snug text-slate-500">
                      ↑ {z.drivers.join(' · ')}
                    </div>
                  )}
                  {pt && (
                    <div className="mt-0.5 text-[9px] text-slate-600">
                      {pt.lat.toFixed(0)}°{pt.lat >= 0 ? 'N' : 'S'}{' '}
                      {Math.abs(pt.lon).toFixed(0)}°{pt.lon >= 0 ? 'E' : 'W'} · {z.description}
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default PressureZones;
