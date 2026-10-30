import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ErrorBar, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EvalData } from "../api/types";
import { isExact, judgeStats, replayId, typeBreakdown } from "../state/arena";
import { useRunStore } from "../state/runStore";

const COLORS: Record<string, string> = { gemma: "#2dd4bf", "pixel-crop": "#8b95a9", "pixel-full": "#5b6579" };

export function JudgeArena() {
  const source = useRunStore((s) => s.source);
  const [data, setData] = useState<EvalData | null | undefined>(undefined);
  const [available, setAvailable] = useState<ReadonlySet<string>>(new Set());
  useEffect(() => {
    source?.loadEval().then(setData);
    source?.listRuns().then((r) => setAvailable(new Set(r.map((x) => x.id)))).catch(() => {});
  }, [source]);

  const rows = data?.results ?? [];
  const stats = useMemo(() => judgeStats(rows), [rows]);
  const types = useMemo(() => [...new Set(rows.map((r) => r.culprit_type))].sort(), [rows]);
  const cases = useMemo(() => {
    const seeds = [...new Set(rows.map((r) => r.seed))].sort((a, b) => a - b);
    return seeds.map((seed) => ({ seed, rows: rows.filter((r) => r.seed === seed) }));
  }, [rows]);

  if (data === undefined) return <div className="p-8 text-dim animate-pulse">Loading results…</div>;
  if (data === null || rows.length === 0) {
    return <div className="p-8 text-dim">No evaluation results yet. Run <span className="mono">eval/run_eval.py</span> to produce <span className="mono">eval/results.json</span>.</div>;
  }
  const seeds = stats[0]?.seeds ?? 0;
  const chart = stats.map((s) => ({ ...s, label: s.name }));

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-xl font-semibold">Judge Arena</h1>
          <p className="text-sm text-dim">{data.label} set · {seeds} repos · exact culprit found, mean over repeats with min–max whiskers</p>
        </div>

        <div className="grid grid-cols-[1.2fr_1fr] gap-8">
          <div className="h-72 rounded-xl border border-line bg-panel p-4">
            <ResponsiveContainer>
              <BarChart data={chart} margin={{ top: 24, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid stroke="#232b3b" vertical={false} />
                <XAxis dataKey="label" stroke="#8b95a9" />
                <YAxis stroke="#8b95a9" domain={[0, seeds]} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#131823", border: "1px solid #232b3b" }} cursor={{ fill: "#ffffff08" }}
                  formatter={(v: number) => [`${v.toFixed(1)} / ${seeds}`, "exact"]} />
                <Bar dataKey="mean" radius={[6, 6, 0, 0]} isAnimationActive={false}
                  shape={(p: any) => <rect x={p.x} y={p.y} width={p.width} height={p.height} rx={6} fill={COLORS[p.judge] ?? "#8b95a9"} />}>
                  <ErrorBar dataKey="err" stroke="#e6e9f0" width={8} />
                  <LabelList dataKey="mean" position="top" fill="#e6e9f0" formatter={(v: number) => `${v.toFixed(1)}/${seeds}`} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <table className="text-sm self-start">
            <thead><tr className="text-dim text-left"><th className="pb-2 font-normal">Judge</th><th className="font-normal">Per-step</th><th className="font-normal">Steps</th><th className="font-normal">Skips</th><th className="font-normal">Time</th></tr></thead>
            <tbody>
              {stats.map((s) => (
                <tr key={s.judge} className="border-t border-line">
                  <td className="py-2 font-semibold" style={{ color: COLORS[s.judge] }}>{s.name}</td>
                  <td>{s.stepAcc == null ? "n/a" : `${Math.round(s.stepAcc * 100)}%`}</td>
                  <td>{s.steps.toFixed(1)}</td><td>{s.skips.toFixed(1)}</td>
                  <td>{s.seconds == null ? "-" : `${Math.round(s.seconds)} s`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <section>
          <h2 className="font-semibold mb-2">By culprit type</h2>
          <table className="text-sm w-full max-w-3xl">
            <thead><tr className="text-dim text-left"><th className="pb-2 font-normal">Type</th>{stats.map((s) => <th key={s.judge} className="font-normal">{s.name}</th>)}</tr></thead>
            <tbody>
              {types.map((t) => (
                <tr key={t} className="border-t border-line">
                  <td className="py-2">{t}</td>
                  {stats.map((s) => {
                    const b = typeBreakdown(rows, s.judge, t);
                    return <td key={s.judge} className="mono">{b.exact}/{b.total}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h2 className="font-semibold mb-2">Test cases</h2>
          <div className="grid grid-cols-3 gap-2">
            {cases.map((c) => (
              <div key={c.seed} className="rounded-lg border border-line bg-panel p-3 text-sm">
                <div className="flex justify-between mb-1.5"><span className="mono">seed {c.seed}</span><span className="text-dim">{c.rows[0].culprit_type}</span></div>
                <div className="flex gap-2 flex-wrap">
                  {stats.map((s) => {
                    const rs = c.rows.filter((r) => r.judge === s.judge);
                    const hit = rs.filter((r) => isExact(r)).length;
                    const run = replayId(rs[0]?.run, available);
                    const chip = (
                      <span className="px-2 py-0.5 rounded text-xs mono" style={{ background: hit === rs.length ? "#2dd4bf22" : hit ? "#8b95a933" : "#fb734033",
                        color: hit === rs.length ? "var(--color-old)" : hit ? "var(--color-dim)" : "var(--color-new)" }}>
                        {s.name} {hit}/{rs.length}
                      </span>
                    );
                    return run ? <a key={s.judge} href={`#/replay/${run}`} title="open replay">{chip}</a> : <span key={s.judge}>{chip}</span>;
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
