import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { liveSource } from "./api/live";
import { staticSource } from "./api/static";
import { useRunStore } from "./state/runStore";
import App from "./App";

// Pick the backend: FastAPI if it answers, otherwise the bundled static export.
async function pickSource() {
  try {
    const r = await fetch("/api/runs", { cache: "no-store" });
    if (r.ok && (r.headers.get("content-type") ?? "").includes("json")) return liveSource;
  } catch { /* fall through */ }
  return staticSource;
}

pickSource().then((src) => {
  useRunStore.getState().setSource(src);
  createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
});
