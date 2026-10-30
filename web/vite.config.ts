import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// base "./" so the exported static site works from a GitHub Pages sub-path.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  // Built into the Python package so wheels ship the UI.
  build: { outDir: "../vbisect/web_dist", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "node" },
});
