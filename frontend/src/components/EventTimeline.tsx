import React from 'react';
import type { EventItem } from '../api/client';

interface EventTimelineProps {
  events: EventItem[];
}

const severityDot = (severity: string): string => {
  switch (severity.toLowerCase()) {
    case 'high':
      return 'bg-rose-500';
    case 'medium':
      return 'bg-amber-400';
    default:
      return 'bg-sky-500';
  }
};

const EventTimeline: React.FC<EventTimelineProps> = ({ events }) => {
  const recent = [...events]
    .sort((a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime())
    .slice(0, 8);

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-700/60 bg-slate-900/80 p-4 backdrop-blur">
      <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-slate-400">
        Event Timeline
      </h2>
      {recent.length === 0 ? (
        <p className="text-sm text-slate-500">No recent events.</p>
      ) : (
        <div className="relative ml-2 space-y-4 overflow-y-auto border-l border-slate-700 pl-4 pr-1">
          {recent.map((event) => (
            <div key={event.id} className="relative">
              <div
                className={`absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full ${severityDot(
                  event.severity
                )}`}
              />
              <div className="text-[10px] uppercase tracking-wide text-slate-500">
                {new Date(event.event_date).toLocaleString()} · {event.region_name}
              </div>
              <div className="text-sm font-medium leading-snug text-slate-100">
                {event.description ?? event.event_type}
              </div>
              <div className="text-[10px] uppercase text-slate-500">
                {event.category} · {event.severity}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EventTimeline;
