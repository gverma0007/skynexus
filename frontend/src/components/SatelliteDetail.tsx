import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { SatelliteDetail } from '../api/client';
import { satCategoryOf, SAT_CATEGORIES } from '../lib/satellites';

interface SatelliteDetailCardProps {
  noradId: number;
  onClose: () => void;
}

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex items-baseline justify-between gap-3">
    <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
    <span className="font-mono text-xs text-slate-200">{value}</span>
  </div>
);

const SatelliteDetailCard: React.FC<SatelliteDetailCardProps> = ({ noradId, onClose }) => {
  const [detail, setDetail] = useState<SatelliteDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    const load = async () => {
      try {
        const data = await api.getSatelliteDetail(noradId);
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load');
      }
    };
    load();
    const interval = setInterval(load, 30000); // position refreshes each cycle
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [noradId]);

  const meta = detail ? SAT_CATEGORIES[satCategoryOf(detail.category)] : null;

  return (
    <div className="absolute left-3 top-3 z-30 w-80 rounded-xl border border-slate-600/70 bg-slate-900/95 p-4 shadow-2xl backdrop-blur">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {meta && <span className={`h-2.5 w-2.5 rotate-45 ${meta.tailwind}`} />}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              NORAD {noradId}
            </div>
            <h3 className="text-base font-black leading-tight text-slate-100">
              {detail?.name ?? 'Loading…'}
            </h3>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded px-1.5 text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-200"
        >
          ✕
        </button>
      </div>

      {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}

      {detail && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-slate-800/60 p-2">
              <div className="text-[9px] uppercase tracking-wider text-slate-500">Altitude</div>
              <div className="font-mono font-bold text-slate-100">
                {detail.position ? `${detail.position.alt_km.toFixed(0)} km` : '—'}
              </div>
            </div>
            <div className="rounded-lg bg-slate-800/60 p-2">
              <div className="text-[9px] uppercase tracking-wider text-slate-500">Ground pos</div>
              <div className="font-mono font-bold text-slate-100">
                {detail.position
                  ? `${detail.position.lat.toFixed(1)}°, ${detail.position.lon.toFixed(1)}°`
                  : '—'}
              </div>
            </div>
          </div>

          {detail.orbit && (
            <>
              <div className="mt-3 mb-1 text-[9px] font-bold uppercase tracking-widest text-slate-500">
                Orbit
              </div>
              <div className="space-y-1.5">
                <Row label="Inclination" value={`${detail.orbit.inclination_deg}°`} />
                <Row label="Period" value={`${detail.orbit.period_minutes} min`} />
                <Row
                  label="Perigee × Apogee"
                  value={`${detail.orbit.perigee_alt_km.toFixed(0)} × ${detail.orbit.apogee_alt_km.toFixed(0)} km`}
                />
                <Row label="Eccentricity" value={detail.orbit.eccentricity.toFixed(6)} />
                <Row label="Revs / day" value={detail.orbit.mean_motion_revs_per_day} />
                <Row label="RAAN" value={`${detail.orbit.raan_deg}°`} />
              </div>
            </>
          )}

          {detail.orbit && (
            <details className="mt-3">
              <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-widest text-slate-500 hover:text-slate-300">
                TLE elements
              </summary>
              <pre className="mt-1 overflow-x-auto rounded bg-slate-950/80 p-2 font-mono text-[9px] leading-snug text-emerald-300">
                {detail.orbit.tle_line1}
                {'\n'}
                {detail.orbit.tle_line2}
              </pre>
            </details>
          )}

          <div className="mt-3 flex items-center justify-between border-t border-slate-700/60 pt-2 text-[10px] text-slate-600">
            <span>{detail.observations} track points buffered</span>
            {meta && <span>{meta.label}</span>}
          </div>
        </>
      )}
    </div>
  );
};

export default SatelliteDetailCard;
