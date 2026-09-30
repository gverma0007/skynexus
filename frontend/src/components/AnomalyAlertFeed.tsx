import React from 'react';
import { severityOf } from '../lib/severity';
import type { Anomaly, EventItem } from '../api/client';

interface AnomalyAlertFeedProps {
  events: EventItem[];
  anomalies: Anomaly[];
}

const AnomalyAlertFeed: React.FC<AnomalyAlertFeedProps> = ({ events, anomalies }) => {
  const alerts = [
    ...events.map((e) => ({
      id: `evt-${e.id}`,
      timestamp: e.event_date,
      message: `${e.event_type} — ${e.region_name}${e.description ? `: ${e.description}` : ''}`,
      severity: e.severity.toLowerCase() as 'high' | 'medium' | 'low',
    })),
    ...anomalies
      .filter((a) => severityOf(a.composite_score ?? 0) !== 'normal')
      .map((a) => ({
        id: `anm-${a.id}`,
        timestamp: a.timestamp,
        message: `${a.entity_type} anomaly in ${a.feature_name} (score ${(
          a.composite_score ?? 0
        ).toFixed(0)})`,
        severity: severityOf(a.composite_score ?? 0),
      })),
  ]
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 20);

  const severityColor = (severity: string) => {
    switch (severity) {
      case 'high':
        return 'text-rose-400';
      case 'medium':
        return 'text-amber-400';
      default:
        return 'text-sky-400';
    }
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-slate-400">
        Anomaly Alerts
      </h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-slate-500">No recent alerts.</p>
      ) : (
        <ul className="space-y-3 overflow-y-auto pr-1">
          {alerts.map((alert) => (
            <li key={alert.id} className="border-b border-slate-700/50 pb-2 last:border-0">
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>{new Date(alert.timestamp).toLocaleString()}</span>
                <span className={`font-bold uppercase ${severityColor(alert.severity)}`}>
                  {alert.severity}
                </span>
              </div>
              <p className="mt-0.5 text-xs leading-snug text-slate-200">{alert.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default AnomalyAlertFeed;
