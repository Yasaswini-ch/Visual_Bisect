import { create } from "zustand";
import type { DataSource } from "../api/source";
import type { RunEvent } from "../api/types";

/** Replay clock: virtual time of each event, long gaps (builds, API waits) compressed. */
export const MAX_GAP_MS = 2500;
export function eventTimes(events: RunEvent[]): number[] {
  const out: number[] = [];
  let t = 0;
  events.forEach((e, i) => {
    if (i > 0) t += Math.min(Math.max(e.ts - events[i - 1].ts, 0.05) * 1000, MAX_GAP_MS);
    out.push(t);
  });
  return out;
}

interface RunStore {
  source: DataSource | null;
  runId: string | null;
  events: RunEvent[];
  /** How many events are visible. Live: all of them. Replay: driven by the clock. */
  cursor: number;
  mode: "live" | "replay";
  times: number[];
  playing: boolean;
  speed: 1 | 2 | 4;
  pos: number;
  selectedSha: string | null;
  loadError: string | null;
  setSource: (s: DataSource) => void;
  openRun: (id: string, mode: "live" | "replay") => () => void;
  push: (e: RunEvent) => void;
  select: (sha: string | null) => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (s: 1 | 2 | 4) => void;
  seek: (pos: number) => void;
  tick: (dtMs: number) => void;
}

const cursorFor = (times: number[], pos: number) => {
  let n = 0;
  while (n < times.length && times[n] <= pos) n++;
  return n;
};

export const useRunStore = create<RunStore>((set, get) => ({
  source: null, runId: null, events: [], cursor: 0, mode: "live", times: [], playing: false, speed: 1, pos: 0,
  selectedSha: null, loadError: null,
  setSource: (source) => set({ source }),

  openRun(id, mode) {
    const { source } = get();
    set({ runId: id, events: [], cursor: 0, mode, times: [], playing: false, pos: 0, selectedSha: null, loadError: null });
    if (!source) return () => {};
    let unsub = () => {};
    let alive = true;
    const load = async (first: boolean) => {
      try {
        const events = await source.loadEvents(id);
        if (!alive) return;
        const times = eventTimes(events);
        if (mode === "replay") set({ events, times, cursor: cursorFor(times, 0), pos: 0, playing: first });
        else set({ events, times, cursor: events.length });
        return events;
      } catch (e) {
        if (alive) set({ loadError: String(e) });
      }
    };
    load(true).then((events) => {
      if (!alive || mode === "replay" || !source.live) return;
      const finished = events?.some((e) => e.type === "run_done" || e.type === "run_failed");
      if (finished) return;
      // The stream replays from the start and push() drops duplicates, so a reconnect just reloads.
      unsub = source.subscribe(id, (e) => get().push(e), () => { load(false); });
    });
    return () => { alive = false; unsub(); };
  },

  push(e) {
    const key = (x: RunEvent) => `${x.ts}|${x.type}|${"sha" in x ? x.sha : ""}|${"call_no" in x ? x.call_no : ""}`;
    const cur = get().events;
    if (cur.some((x) => key(x) === key(e))) return;
    const events = [...cur, e];
    set({ events, times: eventTimes(events), cursor: events.length });
  },
  select: (selectedSha) => set({ selectedSha }),
  setPlaying: (playing) => {
    const { pos, times } = get();
    const end = times[times.length - 1] ?? 0;
    set(playing && pos >= end ? { playing, pos: 0, cursor: 0 } : { playing });
  },
  setSpeed: (speed) => set({ speed }),
  seek(pos) {
    const { times } = get();
    set({ pos, cursor: cursorFor(times, pos) });
  },
  tick(dt) {
    const { pos, speed, times, playing } = get();
    if (!playing) return;
    const end = times[times.length - 1] ?? 0;
    const next = Math.min(pos + dt * speed, end);
    set({ pos: next, cursor: cursorFor(times, next), playing: next < end });
  },
}));
