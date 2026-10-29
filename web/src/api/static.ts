import type { DataSource } from "./source";
import type { EvalData, RunEvent, RunSummary } from "./types";

/** Reads the bundle written by `vbisect export`: data/index.json, data/eval.json, data/runs/<id>/... */
export const staticSource: DataSource = {
  live: false,
  async listRuns() {
    const r = await fetch("data/index.json");
    return r.ok ? ((await r.json()) as RunSummary[]) : [];
  },
  async loadEvents(id) {
    const text = await (await fetch(`data/runs/${id}/events.jsonl`)).text();
    return text.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l) as RunEvent);
  },
  subscribe: () => () => {},
  fileUrl: (id, path) => `data/runs/${id}/${path}`,
  async loadEval() {
    const r = await fetch("data/eval.json");
    return r.ok ? ((await r.json()) as EvalData) : null;
  },
};
