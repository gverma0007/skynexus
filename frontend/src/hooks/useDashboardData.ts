import { useCallback, useEffect, useState } from 'react';
import type {
  EventItem,
  PressureZone,
  RegionDisruption,
  RegionMapPoint,
  RegionOutline,
  StatsSummary,
} from '../api/client';
import { api } from '../api/client';
import { applyBands } from '../lib/severity';

export const useDashboardData = () => {
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [regions, setRegions] = useState<RegionMapPoint[]>([]);
  const [outlines, setOutlines] = useState<RegionOutline[]>([]);
  const [disruptions, setDisruptions] = useState<RegionDisruption[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [pressureZones, setPressureZones] = useState<PressureZone[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r, o, d, e, pz] = await Promise.all([
        api.getStats(),
        api.getRegionsMap(),
        api.getRegionOutlines(),
        api.getDisruptionIndex(),
        api.getEvents(),
        api.getPressureZones(),
      ]);
      setStats(s);
      applyBands(s.severity_bands);
      setRegions(r);
      setOutlines(o);
      setDisruptions(d);
      setEvents(e);
      setPressureZones(pz);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 60000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { stats, regions, outlines, disruptions, events, pressureZones, loading, error, refresh };
};
