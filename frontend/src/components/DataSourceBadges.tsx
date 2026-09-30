import React from 'react';
import type { IngestStatus, SourceInfo } from '../hooks/useIngestStatus';

const DOMAIN_ICON: Record<SourceInfo['domain'], string> = {
  flights: '✈',
  satellites: '🛰',
  weather: '气象',
  events: '⚠',
};

const SOURCE_LABEL: Record<string, string> = {
  'adsb.lol': 'ADS-B',
  'celestrak+sgp4': 'Celestrak',
  'open-meteo': 'Open-Meteo',
  usgs: 'USGS',
  demo_dataset: 'Demo',
};

function freshness(latest: string): { color: string; label: string } {
  const ageMin = (Date.now() - new Date(latest).getTime()) / 60000;
  if (ageMin < 15) return { color: 'bg-emerald-500', label: 'live' };
  if (ageMin < 60) return { color: 'bg-sky-400', label: '<1h' };
  if (ageMin < 24 * 60) return { color: 'bg-amber-400', label: '<24h' };
  return { color: 'bg-slate-500', label: 'stale' };
}

const Badge: React.FC<{ info: SourceInfo }> = ({ info }) => {
  const isLive = info.source !== 'demo_dataset';
  const fresh = freshness(info.latest);
  return (
    <div
      className="flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/70 px-2.5 py-0.5 text-[10px]"
      title={`${info.source} · ${info.count} records · latest ${info.latest}`}
    >
      <span>{DOMAIN_ICON[info.domain]}</span>
      <span className="font-semibold text-slate-300">
        {SOURCE_LABEL[info.source] ?? info.source}
      </span>
      <span
        className={`h-1.5 w-1.5 rounded-full ${isLive ? fresh.color : 'bg-purple-400'}`}
      />
      <span className="text-slate-500">{info.count}</span>
    </div>
  );
};

const DataSourceBadges: React.FC<{ status: IngestStatus | null }> = ({ status }) => {
  if (!status?.sources?.length) return null;

  // Group to one badge per source (domains share sources)
  const bySource = new Map<string, SourceInfo>();
  for (const s of status.sources) {
    const existing = bySource.get(s.source);
    if (!existing || s.count > existing.count) bySource.set(s.source, s);
  }
  const live = [...bySource.values()].filter((s) => s.source !== 'demo_dataset');
  const demo = bySource.get('demo_dataset');
  const ordered = [...live, ...(demo ? [demo] : [])];
  const running = status.state.running;

  return (
    <div className="flex items-center gap-1.5">
      {running && (
        <span className="flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-bold text-sky-300">
          <span className="h-1.5 w-1.5 animate-ping rounded-full bg-sky-400" />
          ingesting…
        </span>
      )}
      {ordered.map((s) => (
        <Badge key={s.source} info={s} />
      ))}
      {status.state.last_error && (
        <span
          className="rounded-full border border-rose-500/40 bg-rose-500/10 px-2 py-0.5 text-[10px] text-rose-300"
          title={status.state.last_error}
        >
          ingest error
        </span>
      )}
    </div>
  );
};

export default DataSourceBadges;
