import { useEffect, useState } from 'react';

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
        if (!cancelled) setStatus(data);
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
