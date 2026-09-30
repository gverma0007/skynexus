import { useEffect, useState } from 'react';
import { SAT_CATEGORIES } from '../lib/satellites';

export interface SourceInfo {
  domain: 'flights' | 'satellites' | 'weather' | 'events';
  source: string;
  count: number;
  latest: string;
}

export interface IngestStatus {
  state: {
    running: boolean;
    last_finished: string | null;
    last_summary: Record<string, number> | null;
    last_error: string | null;
    duration_s: number | null;
  };
  sources: SourceInfo[];
  satellite_categories?: Record<string, number>;
}

export const useIngestStatus = () => {
  const [status, setStatus] = useState<IngestStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/ingest/status');
        if (!res.ok) return;
        const data = (await res.json()) as IngestStatus;
        if (!cancelled) {
          // Ensure every known category shows a count (0 default).
          const cats: Record<string, number> = {};
          for (const key of Object.keys(SAT_CATEGORIES)) {
            cats[key] = data.satellite_categories?.[key] ?? 0;
          }
          data.satellite_categories = cats;
          setStatus(data);
        }
      } catch {
        // status is non-critical; ignore
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return status;
};
