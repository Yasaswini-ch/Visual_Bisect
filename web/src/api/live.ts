import type { DataSource } from "./source";
import { apiToken, withToken } from "./token";
import type { RunEvent } from "./types";

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { "X-VBisect-Token": apiToken() } });
  if (r.status === 401) throw new Error("The dashboard token was rejected. Open the URL that `vbisect serve` prints.");
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
      es = new EventSource(withToken(`/api/runs/${id}/stream`));
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
  fileUrl: (id, path) => withToken(`/api/runs/${id}/files/${path}`),
  async loadEval() {
    try { return await json("/api/eval"); } catch { return null; }
  },
};
