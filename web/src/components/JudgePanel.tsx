import type { RunState, Step } from "../state/derive";
import { useFile } from "../state/useRun";
import { Badge, short } from "./bits";
import { Typewriter } from "./Typewriter";
import { VoteBars } from "./VoteBars";

function Shot({ label, src, tint, note }: { label: string; src?: string | null; tint: string; note?: string }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-1 text-xs">
        <span className="font-semibold tracking-wide" style={{ color: tint }}>{label}</span>
        {note && <span className="mono text-dim">{note}</span>}
      </div>
      <div className="aspect-video rounded-lg overflow-hidden border border-line bg-panel grid place-items-center">
        {src ? <img src={src} alt={label} className="w-full h-full object-cover" />
          : <span className="text-dim text-sm animate-pulse">rendering…</span>}
      </div>
    </div>
  );
}

export function JudgePanel({ st, step, fresh }: { st: RunState; step: Step | undefined; fresh: boolean }) {
  const file = useFile();
  const last = step?.calls[step.calls.length - 1];
  return (
    <div className="px-5 space-y-3">
      <div className="text-sm"><span className="text-dim">Looking for: </span>{st.focus}</div>
      <div className="flex gap-4">
        <Shot label="OLD" src={file(st.oldImg)} tint="var(--color-old)" />
        <Shot label="CANDIDATE" src={step?.img ? file(step.img) : null} tint="#cbd5e1" note={step ? short(step.sha) : undefined} />
        <Shot label="NEW" src={file(st.newImg)} tint="var(--color-new)" />
      </div>
      <div className="flex gap-6 items-start min-h-[92px]">
        <div className="flex-1 space-y-2">
          <div className="text-sm leading-snug min-h-[40px]">
            {step?.skipReason && !last ? <span className="text-skip">Skipped: {step.skipReason}</span>
              : last ? <Typewriter key={`${step!.sha}-${last.call_no}`} text={last.reason} animate={fresh} />
              : <span className="text-dim">The judge's reasoning appears here.</span>}
          </div>
          {step && step.calls.length > 0 && <VoteBars calls={step.calls} />}
        </div>
        <div className="w-24 text-center pt-1"><Badge v={step ? step.verdict : null} big /></div>
      </div>
    </div>
  );
}
