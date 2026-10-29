import { useEffect, useState } from "react";
import { CommitStrip } from "../components/CommitStrip";
import { JudgePanel } from "../components/JudgePanel";
import { Player } from "../components/Player";
import { StatusLine } from "../components/StatusLine";
import { StepTimeline } from "../components/StepTimeline";
import { fmtSec } from "../components/bits";
import { useRunStore } from "../state/runStore";
import { useRunState } from "../state/useRun";
import { Culprit } from "./Culprit";

/** Live Run and Replay are the same screen; only the event source differs. */
export function RunView({ id, mode }: { id: string; mode: "live" | "replay" }) {
  const openRun = useRunStore((s) => s.openRun);
  const selectedSha = useRunStore((s) => s.selectedSha);
  const loadError = useRunStore((s) => s.loadError);
  const st = useRunState();
  const [showCulprit, setShowCulprit] = useState(true);

  useEffect(() => openRun(id, mode), [id, mode, openRun]);
  useEffect(() => { if (st.status !== "done") setShowCulprit(true); }, [st.status]);

  const latest = st.steps[st.steps.length - 1];
  const step = st.steps.find((s) => s.sha === selectedSha) ?? latest;
  const fresh = step === latest && st.status === "running";
  const done = st.status === "done" || st.status === "failed";
  const finishedSteps = st.steps.filter((s) => s.verdict).length;

  if (loadError) return <div className="p-8 text-dim">Could not load run <span className="mono">{id}</span>. {loadError}</div>;
  if (!st.started) return <div className="p-8 text-dim animate-pulse">Waiting for the run to start…</div>;

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-6 px-5 pt-2 text-sm shrink-0">
        <span className="mono text-dim dev-only">{id}</span>
        <span className="font-semibold">Step {Math.min(finishedSteps + (done ? 0 : 1), Math.max(st.estTotal, 1))} of ~{Math.max(st.estTotal, finishedSteps)}</span>
        <span className="text-dim">{fmtSec(st.elapsed)} elapsed</span>
        {st.status === "failed" && <span className="text-new">Run failed: {st.error}</span>}
        {st.status === "done" && st.culpritSha && (
          <button onClick={() => setShowCulprit((v) => !v)} className="ml-auto px-3 py-1 rounded bg-line text-xs cursor-pointer dev-only">
            {showCulprit ? "Show search" : "Show culprit"}
          </button>
        )}
      </div>
      <CommitStrip st={st} />
      <div className="flex-1 min-h-0 grid grid-cols-[1fr_320px] border-t border-line">
        <div className="overflow-y-auto pt-3 pb-4 space-y-3">
          {done && showCulprit ? <Culprit st={st} /> : (
            <>
              <div className="px-5"><StatusLine st={st} step={step} /></div>
              <JudgePanel st={st} step={step} fresh={fresh} />
            </>
          )}
        </div>
        <div className="border-l border-line min-h-0 dev-only"><StepTimeline st={st} shownSha={step?.sha} /></div>
      </div>
      {mode === "replay" && <Player />}
    </div>
  );
}
