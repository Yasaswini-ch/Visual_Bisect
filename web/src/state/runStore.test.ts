import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DataSource } from "../api/source";
import type { RunEvent } from "../api/types";
import { eventTimes, useRunStore } from "./runStore";

const ev = (type: string, ts: number, extra: object = {}) => ({ ts, type, ...extra }) as RunEvent;
const events: RunEvent[] = [
  ev("run_started", 100, { commits: [], good: "g", bad: "b", focus: "", url: "/", old_ref_img: "old.png", new_ref_img: "new.png", judge: "pixel-full", run_id: "r" }),
  ev("step_started", 101, { sha: "a" }),
  ev("step_done", 160, { sha: "a", verdict: "old" }),
  ev("run_done", 161, { culprit_sha: "a", steps: 1, skips: 0, api_calls: 0, seconds: 61, diff_file: null }),
];
const source = (live: boolean): DataSource => ({
  live, listRuns: async () => [], loadEvents: async () => events, subscribe: () => () => {},
  fileUrl: (id, p) => `data/runs/${id}/${p}`, loadEval: async () => null,
});

describe("replay clock", () => {
  it("compresses long gaps and keeps order", () => {
    const t = eventTimes(events);
    expect(t[0]).toBe(0);
    expect(t[2] - t[1]).toBeLessThanOrEqual(2500);
    expect(t).toEqual([...t].sort((a, b) => a - b));
  });
});

describe("static replay navigation", () => {
  beforeEach(() => useRunStore.setState({ source: null, events: [], cursor: 0, pos: 0, playing: false }));

  it("loads a run from a static source, shows the first event, then seeks and plays to the end", async () => {
    useRunStore.getState().setSource(source(false));
    useRunStore.getState().openRun("r", "replay");
    await vi.waitFor(() => expect(useRunStore.getState().events.length).toBe(4));
    expect(useRunStore.getState().cursor).toBe(1);
    const end = useRunStore.getState().times.at(-1)!;
    useRunStore.getState().seek(end);
    expect(useRunStore.getState().cursor).toBe(4);
    useRunStore.getState().setPlaying(true); // at the end: restarts from zero
    expect(useRunStore.getState().pos).toBe(0);
    useRunStore.getState().tick(10_000);
    expect(useRunStore.getState().cursor).toBe(4);
    expect(useRunStore.getState().playing).toBe(false);
  });

  it("builds file URLs relative to the site, so GitHub Pages sub-paths work", () => {
    expect(source(false).fileUrl("r", "renders/x.png")).toBe("data/runs/r/renders/x.png");
  });
});

describe("live push", () => {
  it("drops duplicates delivered again after a reconnect", () => {
    useRunStore.setState({ events: [], cursor: 0 });
    for (const e of [events[0], events[1], events[1], events[2]]) useRunStore.getState().push(e);
    expect(useRunStore.getState().events.length).toBe(3);
    expect(useRunStore.getState().cursor).toBe(3);
  });
});
