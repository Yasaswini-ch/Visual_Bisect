import type { EvalData, RunEvent, RunSummary } from "./types";

/** Every screen talks to this interface only; Live and Static implement it. */
export interface DataSource {
  readonly live: boolean;
  listRuns(): Promise<RunSummary[]>;
  loadEvents(runId: string): Promise<RunEvent[]>;
  /** Live tail. Returns an unsubscribe function. Static sources never call back. */
  subscribe(runId: string, onEvent: (e: RunEvent) => void, onReconnect: () => void): () => void;
  fileUrl(runId: string, path: string): string;
  loadEval(): Promise<EvalData | null>;
}
