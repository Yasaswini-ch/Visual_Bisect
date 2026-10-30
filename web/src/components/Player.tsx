import { useEffect } from "react";
import { useRunStore } from "../state/runStore";
import { fmtSec } from "./bits";

export function Player() {
  const { playing, speed, pos, times, events, setPlaying, setSpeed, seek, tick } = useRunStore();
  const end = times[times.length - 1] ?? 0;

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const id = setInterval(() => { const n = performance.now(); tick(n - last); last = n; }, 50);
    return () => clearInterval(id);
  }, [playing, tick]);

  // Marks on the scrubber where each step finished, to jump between steps.
  const marks = events.map((e, i) => (e.type === "step_done" ? times[i] : null)).filter((t): t is number => t !== null);
  const pct = (t: number) => `${(t / Math.max(end, 1)) * 100}%`;
  return (
    <div className="dev-only flex items-center gap-3 px-5 py-2 border-t border-line bg-panel">
      <button onClick={() => setPlaying(!playing)} aria-label={playing ? "pause" : "play"}
        className="w-9 h-9 rounded-full bg-line hover:bg-[#2f3a52] cursor-pointer">
        {playing ? "❚❚" : "▶"}
      </button>
      <div className="relative flex-1">
        <input type="range" min={0} max={Math.max(end, 1)} value={pos} onChange={(e) => seek(Number(e.target.value))}
          className="w-full accent-[#2dd4bf]" />
        {marks.map((m, i) => (
          <button key={i} title={`jump to step ${i + 1}`} onClick={() => seek(m)}
            className="absolute -top-1.5 w-1.5 h-2.5 bg-new/80 rounded-sm cursor-pointer" style={{ left: `calc(${pct(m)} - 3px)` }} />
        ))}
      </div>
      <span className="mono text-xs text-dim w-28 text-right">{fmtSec(pos / 1000)} / {fmtSec(end / 1000)}</span>
      {([1, 2, 4] as const).map((s) => (
        <button key={s} onClick={() => setSpeed(s)}
          className={`px-2 py-1 text-xs rounded cursor-pointer ${speed === s ? "bg-old text-bg font-bold" : "bg-line text-dim"}`}>{s}×</button>
      ))}
    </div>
  );
}
