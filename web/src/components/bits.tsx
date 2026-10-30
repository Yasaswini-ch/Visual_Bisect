import type { Verdict } from "../api/types";

export const verdictColor = (v: Verdict | "unsure" | null) =>
  v === "old" ? "var(--color-old)" : v === "new" ? "var(--color-new)" : "var(--color-skip)";

export function Badge({ v, big }: { v: Verdict | "unsure" | null; big?: boolean }) {
  const label = v === null ? "…" : v.toUpperCase();
  return (
    <span className={`inline-block rounded font-bold tracking-wide ${big ? "px-4 py-1.5 text-xl" : "px-2 py-0.5 text-xs"}`}
      style={{ color: v ? verdictColor(v) : "var(--color-dim)", border: `1.5px solid ${v ? verdictColor(v) : "var(--color-line)"}`,
        background: v ? `color-mix(in srgb, ${verdictColor(v)} 14%, transparent)` : "transparent" }}>
      {label}
    </span>
  );
}

export const short = (sha: string) => sha.slice(0, 7);
export const fmtSec = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${s.toFixed(1)}s`);
