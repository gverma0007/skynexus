import { useEffect, useState } from 'react';
import type { Anomaly, ForecastResponse, WhatChangedReport } from '../api/client';
import { api } from '../api/client';

export const useAnalysisData = (regionId: string | null) => {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [whatChanged, setWhatChanged] = useState<WhatChangedReport | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!regionId) {
      setAnomalies([]);
      setWhatChanged(null);
      setForecast(null);
      return;
    }

    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      try {
        const [a, w, f] = await Promise.all([
          api.getAnomalies(regionId),
          api.getWhatChanged(regionId),
          api.getForecast(regionId),
        ]);
        if (cancelled) return;
        setAnomalies(a);
        setWhatChanged(w);
        setForecast(f);
      } catch (error) {
        console.error('Failed to fetch analysis data', error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => {
      cancelled = true;
    };
  }, [regionId]);

  return { anomalies, whatChanged, forecast, loading };
};
