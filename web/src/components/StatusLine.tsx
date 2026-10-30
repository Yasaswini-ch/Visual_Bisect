import type { RunState, Step } from "../state/derive";
import { fmtSec } from "./bits";

const LABELS: Record<string, string> = {
  install: "installing", "install-cached": "install (cached)", build: "building", serve: "serving",
};

export function StatusLine({ st, step }: { st: RunState; step: Step | undefined }) {
  if (!step) {
    return <div className="text-sm text-dim h-6">{st.status === "done" ? "Search complete" : "Waiting for the first step…"}</div>;
  }
  const items: { label: string; secs?: number; state: "done" | "active" | "todo" }[] = [];
  const active = step.verdict === null;
  for (const p of step.phases) items.push({ label: LABELS[p.phase] ?? p.phase, secs: p.seconds, state: "done" });
  const hasServe = step.phases.some((p) => p.phase === "serve");
  if (!hasServe && active) {
    items.push({ label: step.phases.some((p) => p.phase === "build") ? "serving" : "building", state: "active" });
  }
  items.push({ label: "rendering", state: step.img ? "done" : hasServe && active ? "active" : "todo" });
  const judgeSecs = step.calls.reduce((a, c) => a + c.seconds, 0);
  items.push({
    label: "judging", secs: step.calls.length ? judgeSecs : undefined,
    state: step.verdict !== null ? "done" : step.img ? "active" : "todo",
  });
  return (
    <div className="flex items-center gap-2 text-sm flex-wrap">
      <span className="mono text-dim mr-1">step {step.no}</span>
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-line">→</span>}
          <span className={it.state === "active" ? "text-ink animate-pulse" : it.state === "done" ? "text-old" : "text-dim"}>
            {it.state === "done" ? "✓ " : ""}{it.label}{it.secs !== undefined ? ` ${fmtSec(it.secs)}` : ""}
          </span>
        </span>
      ))}
    </div>
  );
}
