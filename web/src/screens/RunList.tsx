import { useEffect, useState } from "react";
import type { RunSummary } from "../api/types";
import { fmtSec, short } from "../components/bits";
import { useRunStore } from "../state/runStore";

const STATUS: Record<string, string> = { running: "var(--color-old)", done: "var(--color-dim)", failed: "var(--color-new)" };

export function RunList() {
  const source = useRunStore((s) => s.source);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  useEffect(() => {
    const load = () => source?.listRuns().then(setRuns).catch(() => setRuns([]));
    load();
    const id = source?.live ? setInterval(load, 3000) : undefined;
    return () => clearInterval(id);
  }, [source]);

  if (!runs) return <div className="p-8 text-dim animate-pulse">Loading runs…</div>;
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">Runs</h1>
      {runs.length === 0 && <div className="text-dim">No runs yet. Start one with <span className="mono">vbisect --repo … --ui</span>.</div>}
      <div className="space-y-2">
        {runs.map((r) => (
          <div key={r.id} className="flex items-center gap-4 p-4 rounded-xl border border-line bg-panel">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: STATUS[r.status] }} title={r.status} />
            <div className="min-w-0 flex-1">
              <div className="truncate">{r.focus ?? r.id}</div>
              <div className="text-xs text-dim mono">
                {r.id} · {r.commits} commits · {r.judge}
                {r.culprit && <> · culprit {short(r.culprit)}</>}
                {r.seconds != null && <> · {fmtSec(r.seconds)}</>}
              </div>
            </div>
            {source?.live && r.status === "running" && <a href={`#/run/${r.id}`} className="px-3 py-1.5 rounded bg-old text-bg text-sm font-semibold">Watch live</a>}
            <a href={`#/replay/${r.id}`} className="px-3 py-1.5 rounded bg-line text-sm hover:bg-[#2f3a52]">Replay</a>
          </div>
        ))}
      </div>
    </div>
  );
}
