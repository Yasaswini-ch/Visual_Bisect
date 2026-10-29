import { motion } from "framer-motion";
import { CompareView } from "../components/CompareView";
import { DiffView } from "../components/DiffView";
import { short } from "../components/bits";
import type { RunState } from "../state/derive";
import { useFile } from "../state/useRun";

export function Culprit({ st }: { st: RunState }) {
  const file = useFile();
  const commit = st.commits.find((c) => c.sha === st.culpritSha);

  // Honest fallback: skips blocked a single answer, so show the commits still in play.
  if (!commit) {
    const range = st.commits.slice(st.lo + 1, st.hi + 1);
    return (
      <div className="p-6 max-w-3xl">
        <div className="text-lg font-semibold mb-1">Could not narrow to a single commit</div>
        <div className="text-sm text-dim mb-4">Some commits could not be built or judged, so the culprit is one of these {range.length}:</div>
        <ul className="space-y-1">
          {range.map((c) => (
            <li key={c.sha} className="mono text-sm"><span className="text-dim">{short(c.sha)}</span> {c.subject}</li>
          ))}
        </ul>
      </div>
    );
  }

  const idx = st.commits.indexOf(commit);
  const render = (i: number) => st.steps.find((s) => s.sha === st.commits[i]?.sha && s.img)?.img ?? null;
  const beforeStep = st.steps.filter((s) => s.verdict === "old" && s.img).sort(
    (a, b) => st.commits.findIndex((c) => c.sha === b.sha) - st.commits.findIndex((c) => c.sha === a.sha))[0];
  const beforeSrc = file(beforeStep?.img ?? st.oldImg);
  const afterSrc = file(render(idx) ?? st.newImg);
  const beforeLabel = beforeStep ? `last commit judged OLD (${short(beforeStep.sha)})` : "your OLD screenshot";
  const afterLabel = `culprit ${short(commit.sha)}`;
  const diffFile = st.summary?.diff_file;

  return (
    <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
      className="p-5 grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-6 items-start">
      <div className="rounded-xl border border-new/60 bg-panel p-4 xl:sticky top-0" style={{ boxShadow: "0 0 30px color-mix(in srgb, var(--color-new) 22%, transparent)" }}>
        <div className="text-xs uppercase tracking-widest text-new mb-2">Culprit commit</div>
        <div className="mono text-2xl mb-2">{short(commit.sha)}</div>
        <div className="text-lg leading-snug mb-3">{commit.subject}</div>
        <div className="text-sm text-dim">{commit.author}</div>
        <div className="text-sm text-dim mb-4">{new Date(commit.date).toLocaleString()}</div>
        {st.summary && (
          <div className="grid grid-cols-2 gap-2 text-center border-t border-line pt-3">
            {[["steps", st.summary.steps], ["skips", st.summary.skips], ["API calls", st.summary.api_calls], ["seconds", Math.round(st.summary.seconds)]].map(([k, v]) => (
              <div key={k as string}><div className="text-xl font-semibold">{v}</div><div className="text-xs text-dim">{k}</div></div>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-5 min-w-0">
        <CompareView before={beforeSrc} after={afterSrc} beforeLabel={beforeLabel} afterLabel={afterLabel} />
        <div className="dev-only">
          <div className="text-sm text-dim mb-2">What changed in the code</div>
          {diffFile ? <DiffView url={file(diffFile)} /> : <div className="text-sm text-dim">No diff recorded for this run.</div>}
        </div>
      </div>
    </motion.div>
  );
}
