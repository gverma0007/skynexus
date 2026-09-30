import { useEffect, useState } from 'react';
import './App.css';
import { Globe } from './three/Globe';
import { TopStatBar } from './components/TopStatBar';
import { DisruptionGauge } from './components/DisruptionGauge';
import RegionalAnomalyList from './components/RegionalAnomalyList';
import AnomalyAlertFeed from './components/AnomalyAlertFeed';
import EventTimeline from './components/EventTimeline';
import AIAssessmentPanel from './components/AIAssessmentPanel';
import ForecastPanel from './components/ForecastPanel';
import WhatChangedModal from './components/WhatChangedModal';
import RegionDrawer from './components/RegionDrawer';
import Legend from './components/Legend';
import DataSourceBadges from './components/DataSourceBadges';
import { useIngestStatus } from './hooks/useIngestStatus';
import { useDashboardData } from './hooks/useDashboardData';
import { useLiveTrackingData } from './hooks/useLiveTrackingData';
import { useAnalysisData } from './hooks/useAnalysisData';
import { useSelectionStore } from './hooks/useSelectionStore';

export default function App() {
  const { stats, regions, disruptions, events, loading, error, refresh } = useDashboardData();
  const { flights, satellites } = useLiveTrackingData();
  const selectedRegionId = useSelectionStore((s) => s.selectedRegionId);
  const setSelectedRegionId = useSelectionStore((s) => s.setSelectedRegionId);
  const { anomalies, whatChanged, forecast, loading: analysisLoading } =
    useAnalysisData(selectedRegionId);

  const ingestStatus = useIngestStatus();
  const [modalOpen, setModalOpen] = useState(false);
  const [clock, setClock] = useState<Date | null>(null);

  useEffect(() => {
    // First tick fires after 1s; header shows '—' until then.
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const selectedRegion = regions.find((r) => r.id === selectedRegionId) ?? null;
  const selectedDisruption = disruptions.find((d) => d.region_id === selectedRegionId) ?? null;

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/15 text-sky-400">
            ◈
          </div>
          <div>
            <h1 className="text-sm font-black tracking-widest text-slate-100">SKYNEXUS</h1>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Global Anomaly &amp; Impact Intelligence
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <DataSourceBadges status={ingestStatus} />
          <span className="font-mono text-xs text-slate-400">
            {clock ? clock.toLocaleTimeString() : '—'}
          </span>
          <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            Live
          </span>
          <button
            onClick={() => setModalOpen(true)}
            className="rounded-lg bg-sky-500 px-3.5 py-1.5 text-xs font-bold text-slate-950 transition-colors hover:bg-sky-400"
          >
            What Changed?
          </button>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between border-b border-rose-500/30 bg-rose-500/10 px-5 py-2 text-xs text-rose-300">
          <span>Backend connection issue: {error}</span>
          <button onClick={refresh} className="rounded border border-rose-500/40 px-2 py-0.5 hover:bg-rose-500/10">
            Retry
          </button>
        </div>
      )}

      {/* Stats bar */}
      <div className="relative px-5 pt-4">
        <TopStatBar stats={stats} />
      </div>

      {/* Main content */}
      <main className="grid min-h-0 flex-1 grid-cols-[300px_1fr_340px] gap-4 p-5 pt-16">
        {/* Left panel */}
        <aside className="flex min-h-0 flex-col gap-4">
          <RegionalAnomalyList
            disruptions={disruptions}
            selectedRegionId={selectedRegionId}
            onSelect={setSelectedRegionId}
          />
        </aside>

        {/* Globe */}
        <section className="relative min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-[radial-gradient(ellipse_at_center,#132033_0%,#0b1120_70%)]">
          {loading ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-sm text-slate-500">Initializing global sensor grid…</div>
            </div>
          ) : (
            <Globe
              regions={regions}
              flights={flights}
              satellites={satellites}
              events={events}
              selectedRegionId={selectedRegionId}
              onSelectRegion={setSelectedRegionId}
            />
          )}
          {/* Globe overlays */}
          <div className="pointer-events-none absolute bottom-3 left-3 text-[10px] uppercase tracking-widest text-slate-600">
            Drag to rotate · Click a marker to inspect
          </div>
          <Legend />
          <RegionDrawer
            region={selectedRegion}
            disruption={selectedDisruption}
            onClose={() => setSelectedRegionId(null)}
            onWhatChanged={() => setModalOpen(true)}
          />
        </section>

        {/* Right panel */}
        <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
          <DisruptionGauge
            value={selectedDisruption?.composite_index ?? stats?.global_disruption_index ?? 0}
            label={selectedDisruption ? `${selectedDisruption.region_name} Index` : 'Global Index'}
          />
          <div className="min-h-[180px] flex-1">
            <AnomalyAlertFeed events={events} anomalies={anomalies} />
          </div>
          <EventTimeline events={events} />
        </aside>
      </main>

      {/* Bottom strip */}
      <div className="grid grid-cols-[300px_1fr_340px] gap-4 px-5 pb-4">
        <div />
        <AIAssessmentPanel report={whatChanged} loading={analysisLoading} />
        <ForecastPanel forecast={forecast} />
      </div>

      {modalOpen && (
        <WhatChangedModal
          onClose={() => setModalOpen(false)}
          regions={regions.map((r) => ({ id: r.id, name: r.name }))}
          initialRegionId={selectedRegionId}
        />
      )}
    </div>
  );
}
