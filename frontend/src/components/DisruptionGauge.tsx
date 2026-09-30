import React from 'react';
import { getBands, SEVERITY_BG, SEVERITY_TEXT, severityOf } from '../lib/severity';

interface DisruptionGaugeProps {
  value: number; // 0-100
  label?: string;
}

export const DisruptionGauge: React.FC<DisruptionGaugeProps> = ({ value, label = 'Disruption Index' }) => {
  const severity = severityOf(value);
  const band = getBands();
  const bandHint =
    severity === 'high'
      ? `≥ ${band.high}`
      : severity === 'medium'
        ? `${band.medium}–${band.high - 1}`
        : severity === 'low'
          ? `${band.low}–${band.medium - 1}`
          : `< ${band.low}`;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <div className="flex items-baseline justify-between">
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">{label}</h3>
        <span className={`text-[10px] font-bold uppercase tracking-wider ${SEVERITY_TEXT[severity]}`}>
          {severity} <span className="text-slate-600">({bandHint})</span>
        </span>
      </div>
      <div className={`mt-1 text-3xl font-black ${SEVERITY_TEXT[severity]}`}>{value.toFixed(1)}</div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-700/60">
        <div
          className={`h-full rounded-full transition-all duration-700 ${SEVERITY_BG[severity]}`}
          style={{ width: `${Math.max(2, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
};
