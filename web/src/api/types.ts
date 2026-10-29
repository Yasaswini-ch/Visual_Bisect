export type Verdict = "old" | "new" | "skip";

export interface Commit { sha: string; subject: string; date: string; author: string }

interface Base { ts: number }
export type RunEvent = Base & (
  | { type: "run_started"; run_id: string; commits: Commit[]; good: string; bad: string; focus: string;
      url: string; old_ref_img: string; new_ref_img: string; judge: string }
  | { type: "step_started"; sha: string; step_no?: number; est_total?: number }
  | { type: "build_progress"; sha: string; phase: "install" | "install-cached" | "build" | "serve"; seconds: number }
  | { type: "render_done"; sha: string; img: string }
  | { type: "judge_call"; sha: string; call_no: number; order: "normal" | "swapped";
      verdict: "old" | "new" | "unsure"; confidence: number; reason: string; seconds: number }
  | { type: "step_done"; sha: string; verdict: Verdict; skip_reason?: string | null }
  | { type: "run_done"; culprit_sha: string | null; range?: string[]; steps: number; skips: number;
      api_calls: number; seconds: number; diff_file: string | null }
  | { type: "run_failed"; error: string }
);

export interface RunSummary {
  id: string; started: number; focus: string | null; judge: string | null; commits: number;
  status: "running" | "done" | "failed"; culprit: string | null; steps: number | null; seconds: number | null;
}

export interface EvalRow {
  seed: number; judge: string; rep: number; culprit_type: string; difficulty: string; found: boolean;
  exact: number; steps: number; skips: number; api_calls: number; seconds: number | null;
  step_correct: number; step_judged: number; run: string;
}
export interface EvalData { label: string; results: EvalRow[] }
