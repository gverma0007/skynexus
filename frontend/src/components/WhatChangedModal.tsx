import React, { useState } from 'react';
import { api } from '../api/client';
import type { WhatChangedReport } from '../api/client';

interface WhatChangedModalProps {
  onClose: () => void;
  regions: { id: string; name: string }[];
  initialRegionId?: string | null;
}

const MetricCard: React.FC<{
  title: string;
  before: number | string;
  after: number | string;
  deltaPct: number;
  summary: string;
}> = ({ title, before, after, deltaPct, summary }) => {
  const up = deltaPct >= 0;
  const color = Math.abs(deltaPct) < 5 ? 'text-slate-400' : up ? 'text-emerald-400' : 'text-rose-400';
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/50 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{title}</h3>
        <span className={`text-xs font-bold ${color}`}>
          {up ? '▲' : '▼'} {Math.abs(deltaPct).toFixed(1)}%
        </span>
      </div>
      <div className="mt-1 text-sm text-slate-100">
        <span className="text-slate-500">{before} → </span>
        <span className="font-bold">{after}</span>
      </div>
      <p className="mt-1 text-[11px] leading-snug text-slate-400">{summary}</p>
    </div>
  );
};

const WhatChangedModal: React.FC<WhatChangedModalProps> = ({
  onClose,
  regions,
  initialRegionId,
}) => {
  const [regionId, setRegionId] = useState(initialRegionId ?? regions[0]?.id ?? '');
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<WhatChangedReport | null>(null);

  const handleAnalyze = async () => {
    if (!regionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getWhatChanged(regionId, hours);
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100">What Changed?</h2>
            <p className="text-xs text-slate-500">
              Compare the recent window against the previous one for a region.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-200"
          >
            ✕
          </button>
        </div>

        {!report ? (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Region
              </label>
              <select
                value={regionId}
                onChange={(e) => setRegionId(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 p-2.5 text-sm text-slate-100 outline-none focus:border-sky-500"
              >
                {regions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-slate-500">
                Comparison window
              </label>
              <div className="flex gap-2">
                {[6, 24, 72].map((h) => (
                  <button
                    key={h}
                    onClick={() => setHours(h)}
                    className={`flex-1 rounded-lg border px-3 py-2 text-xs font-semibold transition-colors ${
                      hours === h
                        ? 'border-sky-500 bg-sky-500/10 text-sky-300'
                        : 'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    {h}h vs {h * 2}h
                  </button>
                ))}
              </div>
            </div>
            {error && <p className="text-xs text-rose-400">{error}</p>}
            <button
              onClick={handleAnalyze}
              disabled={loading || !regionId}
              className="w-full rounded-lg bg-sky-500 py-2.5 text-sm font-bold text-slate-950 transition-colors hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Analyzing…' : 'Run Analysis'}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="text-xs text-slate-500">
              {report.region.name} · last {report.window_hours}h vs previous {report.window_hours}h
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard
                title="Aviation"
                before={report.aviation_metrics.before}
                after={report.aviation_metrics.after}
                deltaPct={report.aviation_metrics.delta_pct}
                summary={report.aviation_metrics.summary}
              />
              <MetricCard
                title="Satellites"
                before={report.satellite_metrics.before}
                after={report.satellite_metrics.after}
                deltaPct={report.satellite_metrics.delta_pct}
                summary={report.satellite_metrics.summary}
              />
              <MetricCard
                title="Weather"
                before={report.weather_metrics.before}
                after={report.weather_metrics.after}
                deltaPct={report.weather_metrics.delta_pct}
                summary={report.weather_metrics.summary}
              />
              <MetricCard
                title="Events"
                before={report.events_metrics.before}
                after={report.events_metrics.after}
                deltaPct={report.events_metrics.delta_pct}
                summary={report.events_metrics.summary}
              />
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
              <h3 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Overall Assessment
              </h3>
              <p className="text-sm leading-relaxed text-slate-200">{report.overall_assessment}</p>
              <p className="mt-3 text-[10px] italic text-slate-600">
                Correlation does not establish causation.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setReport(null)}
                className="flex-1 rounded-lg border border-slate-700 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-800"
              >
                ← Back
              </button>
              <button
                onClick={onClose}
                className="flex-1 rounded-lg bg-sky-500 py-2 text-sm font-bold text-slate-950 transition-colors hover:bg-sky-400"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WhatChangedModal;
