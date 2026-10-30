import { describe, expect, it } from "vitest";
import type { EvalRow } from "../api/types";
import { isExact, judgeStats, replayId, typeBreakdown } from "./arena";

const row = (o: Partial<EvalRow>): EvalRow => ({ seed: 1, judge: "gemma", rep: 0, culprit_type: "color", difficulty: "obvious",
  found: true, exact: 1, steps: 7, skips: 0, api_calls: 14, seconds: 10, step_correct: 7, step_judged: 7, run: "eval/runs/a", ...o });

describe("eval data", () => {
  it("treats boolean and numeric exact the same", () => {
    expect([isExact(row({ exact: true })), isExact(row({ exact: 1 })), isExact(row({ exact: false })), isExact(row({ exact: 0 }))]).toEqual([1, 1, 0, 0]);
  });
  it("computes mean and min-max whiskers over repeats", () => {
    const rows = [0, 1, 2].flatMap((rep) => [1, 2, 3].map((seed) => row({ rep, seed, exact: rep === 0 ? seed <= 1 : seed <= 3 })));
    const [g] = judgeStats(rows);
    expect([g.min, g.max, g.seeds]).toEqual([1, 3, 3]);
    expect(g.mean).toBeCloseTo(7 / 3);
    expect(g.err[0] + g.min).toBeCloseTo(g.mean);
  });
  it("breaks down by judge and culprit type", () => {
    const rows = [row({ culprit_type: "color" }), row({ culprit_type: "color", exact: false }), row({ culprit_type: "width" }),
      row({ judge: "pixel-full", culprit_type: "color", exact: false })];
    expect(typeBreakdown(rows, "gemma", "color")).toEqual({ exact: 1, total: 2 });
    expect(typeBreakdown(rows, "pixel-full", "color")).toEqual({ exact: 0, total: 1 });
    expect(typeBreakdown(rows, "pixel-full", "width")).toEqual({ exact: 0, total: 0 });
  });
  it("links a case to its replay only when that run is in the export", () => {
    const have = new Set(["seed1-gemma"]);
    expect(replayId("eval/runs/seed1-gemma", have)).toBe("seed1-gemma");
    expect(replayId(["C:", "x", "runs", "seed1-gemma", ""].join(String.fromCharCode(92)), have)).toBe("seed1-gemma");
    expect(replayId("eval/runs/other", have)).toBeNull();
    expect(replayId(undefined, have)).toBeNull();
  });
});
