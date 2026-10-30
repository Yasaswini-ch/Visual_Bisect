import { useEffect, useState } from "react";
import { useRunStore } from "./state/runStore";
import { JudgeArena } from "./screens/JudgeArena";
import { RunList } from "./screens/RunList";
import { RunView } from "./screens/RunView";

function useHash() {
  const [h, setH] = useState(location.hash || "#/");
  useEffect(() => {
    const f = () => setH(location.hash || "#/");
    addEventListener("hashchange", f);
    return () => removeEventListener("hashchange", f);
  }, []);
  return h;
}

export default function App() {
  const hash = useHash();
  const live = useRunStore((s) => s.source?.live);
  const [present, setPresent] = useState(false);

  useEffect(() => {
    document.body.classList.toggle("present", present);
  }, [present]);
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.key === "p" || e.key === "P") && !(e.target instanceof HTMLInputElement)) setPresent((p) => !p);
    };
    addEventListener("keydown", f);
    return () => removeEventListener("keydown", f);
  }, []);

  const [, route, id] = hash.split("/");
  const nav = (to: string, label: string) => (
    <a href={to} className={`px-3 py-1 rounded ${hash === to ? "bg-line text-ink" : "text-dim hover:text-ink"}`}>{label}</a>
  );
  return (
    <div className="h-full flex flex-col">
      <header className="dev-only flex items-center gap-2 px-4 h-11 border-b border-line shrink-0">
        <a href="#/" className="font-semibold tracking-tight mr-4">visual<span className="text-old">-</span>bisect</a>
        {nav("#/", "Runs")}
        {nav("#/arena", "Judge Arena")}
        <span className="ml-auto text-xs text-dim">
          {live ? "live" : "static replay"} · press <kbd className="mono px-1 border border-line rounded">P</kbd> for presentation mode
        </span>
      </header>
      <main className="flex-1 min-h-0">
        {route === "run" && id ? <RunView key={`l${id}`} id={id} mode="live" />
          : route === "replay" && id ? <RunView key={`r${id}`} id={id} mode="replay" />
          : route === "arena" ? <JudgeArena />
          : <RunList />}
      </main>
    </div>
  );
}
