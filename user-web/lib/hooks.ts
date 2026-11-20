'use client';
import { useEffect, useRef, useState } from 'react';
import { ApiError } from './api';
import { useAuth } from './auth';

/** Loads data once and, if intervalMs > 0, re-polls while the tab is visible. 401 signs the user out. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[], intervalMs = 0) {
  const { logout } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [tick, setTick] = useState(0);
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const d = await ref.current();
        if (alive) { setData(d); setError(null); setErr(null); }
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.httpStatus === 401) logout();
        setErr(e);
        setError(e instanceof Error ? e.message : String(e));
      }
    };
    run();
    const id = intervalMs ? setInterval(() => { if (!document.hidden) run(); }, intervalMs) : undefined;
    return () => { alive = false; if (id) clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, intervalMs]);
  return { data, error, err, reload: () => setTick((t) => t + 1) };
}

export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(id); }, [ms]);
  return now;
}
