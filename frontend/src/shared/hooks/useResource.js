import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

export function useResource(path, revision = 0) {
  const [state, setState] = useState({ data: null, loading: true, error: '' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    // A changed endpoint invalidates the previous response until the fetch finishes.
    // oxlint-disable-next-line react/set-state-in-effect
    setState({ data: null, loading: true, error: '' });
    api(path, { signal: controller.signal }).then(data => setState({ data, loading: false, error: '' })).catch(e => {
      if (e.name !== 'AbortError') setState({ data: null, loading: false, error: e.message });
    });
    return () => controller.abort();
  }, [path, revision, attempt]);
  const reload = useCallback(() => setAttempt(v => v + 1), []);
  return { ...state, reload };
}
