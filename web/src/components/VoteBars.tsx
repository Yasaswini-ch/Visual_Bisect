import { motion } from "framer-motion";
import type { Call } from "../state/derive";
import { verdictColor } from "./bits";

export function VoteBars({ calls }: { calls: Call[] }) {
  return (
    <div className="space-y-1.5">
      {calls.map((c, i) => {
        const color = verdictColor(c.verdict === "unsure" ? "skip" : c.verdict);
        return (
          <div key={c.call_no} className="flex items-center gap-3 text-xs">
            <span className="w-28 text-dim shrink-0">
              {i === 2 ? "Tie-breaker" : c.order === "normal" ? "Normal order" : "Swapped order"}
            </span>
            <div className="flex-1 h-3.5 rounded bg-panel overflow-hidden border border-line">
              <motion.div initial={{ width: 0 }} animate={{ width: `${Math.round(c.confidence * 100)}%` }}
                transition={{ duration: 0.4 }} className="h-full" style={{ background: color }} />
            </div>
            <span className="w-24 mono text-right" style={{ color }}>
              {c.verdict.toUpperCase()} {Math.round(c.confidence * 100)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
