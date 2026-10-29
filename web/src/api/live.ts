import type { DataSource } from "./source";
import type { RunEvent } from "./types";

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

export const liveSource: DataSource = {
  live: true,
  listRuns: () => json("/api/runs"),
  loadEvents: (id) => json(`/api/runs/${id}`),
  subscribe(id, onEvent, onReconnect) {
    let es: EventSource | null = null;
    let closed = false;
    const open = () => {
      es = new EventSource(`/api/runs/${id}/stream`);
      es.onmessage = (m) => onEvent(JSON.parse(m.data) as RunEvent);
      es.onerror = () => {
        // The server closes the stream after run_done; only reconnect while we still want it.
        es?.close();
        if (!closed) setTimeout(() => { if (!closed) { onReconnect(); open(); } }, 1500);
      };
    };
    open();
    return () => { closed = true; es?.close(); };
  },
  fileUrl: (id, path) => `/api/runs/${id}/files/${path}`,
  async loadEval() {
    try { return await json("/api/eval"); } catch { return null; }
  },
};
