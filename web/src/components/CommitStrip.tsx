import { motion } from "framer-motion";
import type { RunState } from "../state/derive";
import { isRuledOut } from "../state/derive";
import { short } from "./bits";

export function CommitStrip({ st }: { st: RunState }) {
  const roomy = st.remaining <= 8;
  return (
    <div className="px-5 pt-3 pb-2">
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-sm text-dim">{st.status === "done" && st.culpritSha ? "Found it" : "Remaining range"}</div>
        <div className="text-sm text-dim mono">
          {st.remaining} of {st.commits.length} commits left
        </div>
      </div>
      <div className="flex gap-[3px] h-[72px]">
        {st.commits.map((c, i) => {
          const out = isRuledOut(st, i);
          const testing = st.currentSha === c.sha;
          const culprit = st.culpritSha === c.sha;
          const tested = st.steps.find((s) => s.sha === c.sha && s.verdict);
          const tint = culprit ? "var(--color-new)"
            : tested ? (tested.verdict === "old" ? "var(--color-old)" : tested.verdict === "new" ? "var(--color-new)" : "var(--color-skip)")
            : null;
          return (
            <motion.div key={c.sha} title={`${short(c.sha)} ${c.subject}`}
              initial={false}
              animate={{ flexGrow: out ? 0.22 : culprit ? 6 : 1, opacity: out ? 0.28 : 1, scaleY: out ? 0.55 : 1 }}
              transition={{ duration: 0.38, ease: "easeOut" }}
              className={`basis-0 min-w-[2px] rounded-md overflow-hidden px-1.5 py-1 flex flex-col justify-end ${testing ? "animate-pulse" : ""}`}
              style={{
                background: tint ? `color-mix(in srgb, ${tint} 22%, var(--color-panel))` : "var(--color-panel)",
                border: `1.5px solid ${testing ? "#fff" : tint ?? (out ? "var(--color-line)" : "#3a4660")}`,
                boxShadow: culprit ? "0 0 22px var(--color-new)" : !out && !tint ? "0 0 12px rgba(120,160,255,.18)" : "none",
              }}>
              {!out && (roomy || culprit) && (
                <>
                  <div className="mono text-[11px] text-dim">{short(c.sha)}</div>
                  <div className="text-xs leading-tight truncate">{c.subject}</div>
                </>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
