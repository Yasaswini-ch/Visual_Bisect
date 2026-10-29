import type { Commit, RunEvent, Verdict } from "../api/types";

export interface Call {
  call_no: number; order: "normal" | "swapped"; verdict: "old" | "new" | "unsure";
  confidence: number; reason: string; seconds: number;
}
export interface Step {
  sha: string; no: number; verdict: Verdict | null; skipReason: string | null;
  img: string | null; calls: Call[]; phases: { phase: string; seconds: number }[];
  startedTs: number; doneTs: number | null;
}
export interface RunState {
  started: boolean;
  commits: Commit[];
  focus: string; judge: string; url: string; oldImg: string; newImg: string;
  steps: Step[];
  /** Index of the last commit known to be OLD (-1 if none) and first known NEW (last commit if none). */
  lo: number; hi: number;
  remaining: number;
  currentSha: string | null;
  estTotal: number;
  status: "idle" | "running" | "done" | "failed";
  culpritSha: string | null;
  error: string | null;
  elapsed: number;
  summary: { steps: number; skips: number; api_calls: number; seconds: number; diff_file: string | null } | null;
}

export const emptyState: RunState = {
  started: false, commits: [], focus: "", judge: "", url: "/", oldImg: "", newImg: "", steps: [],
  lo: -1, hi: -1, remaining: 0, currentSha: null, estTotal: 0, status: "idle", culpritSha: null,
  error: null, elapsed: 0, summary: null,
};

/** log2 of the commits left; the number of judged steps still expected, rounded up. */
export function estimateTotal(done: number, remaining: number): number {
  return done + (remaining > 1 ? Math.ceil(Math.log2(remaining)) : 0);
}

/** Everything the UI shows is a pure function of the event list (live and replay always agree). */
export function derive(events: RunEvent[]): RunState {
  const s: RunState = { ...emptyState, steps: [] };
  const byEvent = new Map<string, Step>();
  let firstTs = 0, lastTs = 0;

  for (const e of events) {
    if (!firstTs) firstTs = e.ts;
    lastTs = e.ts;
    switch (e.type) {
      case "run_started":
        Object.assign(s, { started: true, commits: e.commits, focus: e.focus, judge: e.judge, url: e.url,
          oldImg: e.old_ref_img, newImg: e.new_ref_img, status: "running", hi: e.commits.length - 1 });
        break;
      case "step_started": {
        const step: Step = { sha: e.sha, no: s.steps.length + 1, verdict: null, skipReason: null, img: null,
          calls: [], phases: [], startedTs: e.ts, doneTs: null };
        s.steps.push(step); byEvent.set(e.sha, step); s.currentSha = e.sha;
        break;
      }
      case "build_progress": byEvent.get(e.sha)?.phases.push({ phase: e.phase, seconds: e.seconds }); break;
      case "render_done": { const st = byEvent.get(e.sha); if (st) st.img = e.img; break; }
      case "judge_call": {
        const { sha: _s, type: _t, ts: _ts, ...call } = e;
        byEvent.get(e.sha)?.calls.push(call);
        break;
      }
      case "step_done": {
        const st = byEvent.get(e.sha);
        if (st) { st.verdict = e.verdict; st.skipReason = e.skip_reason ?? null; st.doneTs = e.ts; }
        const idx = s.commits.findIndex((c) => c.sha === e.sha);
        if (e.verdict === "old" && idx > s.lo) s.lo = idx;
        if (e.verdict === "new" && idx >= 0 && idx < s.hi) s.hi = idx;
        if (s.currentSha === e.sha) s.currentSha = null;
        break;
      }
      case "run_done":
        s.status = "done"; s.culpritSha = e.culprit_sha; s.currentSha = null;
        s.summary = { steps: e.steps, skips: e.skips, api_calls: e.api_calls, seconds: e.seconds, diff_file: e.diff_file };
        break;
      case "run_failed": s.status = "failed"; s.error = e.error; s.currentSha = null; break;
    }
  }
  s.remaining = s.started ? Math.max(1, s.hi - s.lo) : 0;
  s.estTotal = estimateTotal(s.steps.filter((x) => x.verdict !== null).length, s.remaining);
  s.elapsed = lastTs - firstTs;
  return s;
}

export function isRuledOut(state: RunState, idx: number): boolean {
  return idx <= state.lo || idx > state.hi;
}

/** Fraction of the call's confidence, signed toward the verdict, for the vote bars. */
export function tally(calls: Call[]): { old: number; new: number; unsure: number } {
  const t = { old: 0, new: 0, unsure: 0 };
  for (const c of calls) t[c.verdict]++;
  return t;
}
