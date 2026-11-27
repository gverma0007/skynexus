import { useCallback, useEffect, useRef, useState } from 'react';
import { useViewer, viewer as viewerStore } from './viewer';
import { useActivity } from './activity';

export interface PollState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => void;
}

/** Fetch now, then every `intervalMs` (0 = once). Keeps last good data on error. */
export function usePoll<T>(fn: () => Promise<T>, intervalMs: number, deps: unknown[] = []): PollState<T> {
  const viewer = useViewer();
  const active = useActivity(viewer.profile === 'free_demo');
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  const previousContext = useRef(viewer);
  const previousDependencies = useRef([...deps]);
  const lastRevision = useRef(viewer.revision);
  fnRef.current = fn;
  const seq = useRef(0);

  const run = useCallback(async () => {
    const id = ++seq.current;
    try {
      const result = await fnRef.current();
      if (id !== seq.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (id !== seq.current) return;
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) { ++seq.current; setLoading(false); return; }
    const previous = previousContext.current;
    const changedSelection = deps.length !== previousDependencies.current.length || deps.some((value, index) => !Object.is(value, previousDependencies.current[index]));
    previousDependencies.current = [...deps];
    previousContext.current = viewer;
    if (!viewer.realtime && viewer.dataset !== 'historical' && previous.realtime && previous.dataset === viewer.dataset) {
      ++seq.current;
      setLoading(false);
      return;
    }
    setLoading(true);
    if (changedSelection || previous.dataset !== viewer.dataset) setData(null);
    run();
    if (!intervalMs || !viewer.realtime) return () => { ++seq.current; };
    const t = setInterval(() => {
      if (document.visibilityState === 'visible') run();
    }, intervalMs);
    return () => { ++seq.current; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, viewer.dataset, viewer.realtime, active]);

  useEffect(() => {
    if (lastRevision.current === viewer.revision) return;
    lastRevision.current = viewer.revision;
    const context = viewerStore.get();
    if (active && (context.realtime || context.dataset === 'historical' || context.profile === 'free_demo')) run();
    // Revision changes are pushed by the authenticated SSE stream.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewer.revision]);

  return { data, error, loading, refresh: run };
}
