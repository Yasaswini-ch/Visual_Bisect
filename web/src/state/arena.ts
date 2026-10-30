import type { EvalRow } from "../api/types";

export const JUDGE_NAMES: Record<string, string> = { gemma: "Gemma 4", "pixel-crop": "Pixel-crop", "pixel-full": "Pixel-full" };
export const judgeLabel = (j: string) => JUDGE_NAMES[j] ?? j;
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

/** results.json writes `exact` as a boolean (run_eval.py) or 0/1; both count the same. */
export const isExact = (r: EvalRow) => (r.exact === true || Number(r.exact) === 1 ? 1 : 0);

export function judgeStats(rows: EvalRow[]) {
  const seeds = new Set(rows.map((r) => r.seed)).size;
  const judges = [...new Set(rows.map((r) => r.judge))];
  return judges.map((j) => {
    const rs = rows.filter((r) => r.judge === j);
    const perRep = new Map<number, number>();
    rs.forEach((r) => perRep.set(r.rep, (perRep.get(r.rep) ?? 0) + isExact(r)));
    const reps = [...perRep.values()];
    const judged = rs.reduce((a, r) => a + r.step_judged, 0);
    const times = rs.map((r) => r.seconds).filter((x): x is number => x != null);
    return {
      judge: j, name: judgeLabel(j), seeds, mean: mean(reps), min: Math.min(...reps), max: Math.max(...reps),
      err: [mean(reps) - Math.min(...reps), Math.max(...reps) - mean(reps)] as [number, number],
      stepAcc: judged ? rs.reduce((a, r) => a + r.step_correct, 0) / judged : null,
      steps: mean(rs.map((r) => r.steps)), skips: mean(rs.map((r) => r.skips)), seconds: times.length ? mean(times) : null,
    };
  });
}

/** Exact-culprit count and total for one judge and culprit type. */
export function typeBreakdown(rows: EvalRow[], judge: string, type: string) {
  const sub = rows.filter((r) => r.judge === judge && r.culprit_type === type);
  return { exact: sub.reduce((a, r) => a + isExact(r), 0), total: sub.length };
}

/** results.json stores the run folder path; the replay route needs the folder name, if that run was exported. */
export function replayId(run: string | undefined, available: ReadonlySet<string>): string | null {
  const id = run?.split(/[\\/]/).filter(Boolean).pop();
  return id && available.has(id) ? id : null;
}
