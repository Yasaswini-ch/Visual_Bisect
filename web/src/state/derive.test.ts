import { describe, expect, it } from "vitest";
import type { RunEvent } from "../api/types";
import { derive } from "./derive";

const commits = Array.from({ length: 8 }, (_, i) => ({ sha: `c${i}`, subject: `s${i}`, date: "", author: "a" }));
const base = { ts: 1 };
const start: RunEvent = { ...base, type: "run_started", run_id: "r", commits, good: "g", bad: "c7", focus: "f",
  url: "/", old_ref_img: "old.png", new_ref_img: "new.png", judge: "gemma" };
const step = (sha: string, verdict: "old" | "new" | "skip", ts = 2): RunEvent[] => [
  { ts, type: "step_started", sha }, { ts, type: "step_done", sha, verdict },
];

describe("derive", () => {
  it("narrows the range from verdicts", () => {
    const s = derive([start, ...step("c3", "old"), ...step("c5", "new")]);
    expect([s.lo, s.hi, s.remaining]).toEqual([3, 5, 2]);
  });
  it("ignores out-of-order older verdicts and skips", () => {
    const s = derive([start, ...step("c5", "new"), ...step("c2", "old"), ...step("c1", "old"), ...step("c4", "skip")]);
    expect([s.lo, s.hi]).toEqual([2, 5]);
  });
  it("tracks status and culprit", () => {
    const s = derive([start, ...step("c3", "new"), { ts: 3, type: "run_done", culprit_sha: "c3", steps: 1, skips: 0,
      api_calls: 2, seconds: 5, diff_file: null }]);
    expect(s.status).toBe("done");
    expect(s.culpritSha).toBe("c3");
  });
  it("is empty before run_started", () => expect(derive([]).started).toBe(false));
});
