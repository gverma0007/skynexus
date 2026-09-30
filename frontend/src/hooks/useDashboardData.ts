import { useCallback, useEffect, useState } from 'react';
import type { EventItem, RegionDisruption, RegionMapPoint, StatsSummary } from '../api/client';
import { api } from '../api/client';
import { applyBands } from '../lib/severity';

export const useDashboardData = () => {
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [regions, setRegions] = useState<RegionMapPoint[]>([]);
  const [disruptions, setDisruptions] = useState<RegionDisruption[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r, d, e] = await Promise.all([
        api.getStats(),
        api.getRegionsMap(),
        api.getDisruptionIndex(),
        api.getEvents(),
      ]);
      setStats(s);
      applyBands(s.severity_bands);
      setRegions(r);
      setDisruptions(d);
      setEvents(e);
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

  return { stats, regions, disruptions, events, loading, error, refresh };
};
