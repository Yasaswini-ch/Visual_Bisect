import type { RunState } from "../state/derive";
import { useRunStore } from "../state/runStore";
import { useFile } from "../state/useRun";
import { Badge, short } from "./bits";

export function StepTimeline({ st, shownSha }: { st: RunState; shownSha: string | undefined }) {
  const file = useFile();
  const select = useRunStore((s) => s.select);
  return (
    <div className="h-full overflow-y-auto px-3 py-3 space-y-2">
      <div className="text-sm text-dim px-1">Steps</div>
      {[...st.steps].reverse().map((s) => {
        const reason = s.skipReason ?? s.calls[s.calls.length - 1]?.reason ?? "judging…";
        return (
          <button key={s.sha} onClick={() => select(s.sha)}
            className={`w-full text-left flex gap-3 p-2 rounded-lg border transition-colors cursor-pointer ${shownSha === s.sha ? "border-[#4a5878] bg-panel" : "border-line hover:bg-panel"}`}>
            <div className="w-20 aspect-video rounded overflow-hidden bg-bg border border-line shrink-0">
              {s.img && <img src={file(s.img)} alt="" className="w-full h-full object-cover" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between">
                <span className="mono text-xs text-dim">#{s.no} {short(s.sha)}</span>
                <Badge v={s.verdict} />
              </div>
              <div className="text-xs mt-1 line-clamp-2 text-dim">{reason}</div>
            </div>
          </button>
        );
      })}
      {st.steps.length === 0 && <div className="text-xs text-dim px-1">No steps yet.</div>}
    </div>
  );
}
