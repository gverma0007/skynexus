import React from 'react';
import type { WhatChangedReport } from '../api/client';

interface AIAssessmentPanelProps {
  report: WhatChangedReport | null;
  loading?: boolean;
}

const AIAssessmentPanel: React.FC<AIAssessmentPanelProps> = ({ report, loading }) => {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
        <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
          AI Assessment
        </h2>
      </div>
      {loading ? (
        <div className="mt-3 space-y-2">
          <div className="h-3 w-full animate-pulse rounded bg-slate-700/60" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-slate-700/60" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-slate-700/60" />
        </div>
      ) : report ? (
        <>
          <p className="mt-3 text-sm leading-relaxed text-slate-200">{report.overall_assessment}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-slate-800/60 p-2">
              <span className="text-slate-500">Aviation </span>
              <span
                className={
                  report.aviation_metrics.delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }
              >
                {report.aviation_metrics.delta_pct >= 0 ? '▲' : '▼'}{' '}
                {Math.abs(report.aviation_metrics.delta_pct).toFixed(0)}%
              </span>
            </div>
            <div className="rounded-lg bg-slate-800/60 p-2">
              <span className="text-slate-500">Events </span>
              <span
                className={
                  report.events_metrics.delta_pct >= 0 ? 'text-amber-400' : 'text-sky-400'
                }
              >
                {report.events_metrics.after} active
              </span>
            </div>
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">Select a region to generate an assessment.</p>
      )}
      <p className="mt-3 text-[10px] italic text-slate-600">
        Correlation does not establish causation.
      </p>
    </div>
  );
};

export default AIAssessmentPanel;
