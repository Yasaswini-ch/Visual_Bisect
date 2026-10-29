import { useState } from "react";
import { ReactCompareSlider, ReactCompareSliderImage } from "react-compare-slider";
import { Heatmap } from "./Heatmap";

type Mode = "slider" | "side" | "onion" | "heat";
const MODES: [Mode, string][] = [["slider", "Drag slider"], ["side", "Side by side"], ["onion", "Onion skin"], ["heat", "Difference"]];

export function CompareView({ before, after, beforeLabel, afterLabel }:
  { before: string; after: string; beforeLabel: string; afterLabel: string }) {
  const [mode, setMode] = useState<Mode>("slider");
  const [mix, setMix] = useState(50);
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        {MODES.map(([m, label]) => (
          <button key={m} onClick={() => setMode(m)}
            className={`px-3 py-1 rounded text-xs cursor-pointer ${mode === m ? "bg-old text-bg font-bold" : "bg-line text-dim hover:text-ink"}`}>{label}</button>
        ))}
        <span className="ml-auto text-xs text-dim"><span className="text-old">{beforeLabel}</span> → <span className="text-new">{afterLabel}</span></span>
      </div>
      {mode === "slider" && (
        <ReactCompareSlider className="rounded-lg border border-line overflow-hidden"
          itemOne={<ReactCompareSliderImage src={before} alt={beforeLabel} />}
          itemTwo={<ReactCompareSliderImage src={after} alt={afterLabel} />} />
      )}
      {mode === "side" && (
        <div className="flex gap-3">
          <img src={before} alt={beforeLabel} className="w-1/2 rounded-lg border border-line" />
          <img src={after} alt={afterLabel} className="w-1/2 rounded-lg border border-line" />
        </div>
      )}
      {mode === "onion" && (
        <div>
          <div className="relative rounded-lg border border-line overflow-hidden">
            <img src={before} alt={beforeLabel} className="w-full block" />
            <img src={after} alt={afterLabel} className="w-full block absolute inset-0" style={{ opacity: mix / 100 }} />
          </div>
          <input type="range" min={0} max={100} value={mix} onChange={(e) => setMix(Number(e.target.value))} className="w-full mt-2 accent-[#fb7340]" />
        </div>
      )}
      {mode === "heat" && <Heatmap before={before} after={after} />}
    </div>
  );
}
