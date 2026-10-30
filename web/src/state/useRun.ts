import { useMemo } from "react";
import { derive } from "./derive";
import { useRunStore } from "./runStore";

export function useRunState() {
  const events = useRunStore((s) => s.events);
  const cursor = useRunStore((s) => s.cursor);
  return useMemo(() => derive(events.slice(0, cursor)), [events, cursor]);
}

export function useFile() {
  const source = useRunStore((s) => s.source);
  const runId = useRunStore((s) => s.runId);
  return (path: string) => (source && runId ? source.fileUrl(runId, path) : "");
}
