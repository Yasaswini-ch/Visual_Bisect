"""Live dashboard: reads runs/**/events.jsonl and streams it to the browser (SSE).

Run:  python -m vbisect.server [--runs runs] [--port 8431]   (binds to 127.0.0.1 only)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

STATIC = Path(__file__).parent / "static"


class NewRun(BaseModel):
    repo: str
    good: str
    bad: str = "HEAD"
    focus: str
    url: str = "/"
    judge: str = "gemma"
    preset: str | None = None
    model: str | None = None
    screenshot: str | None = None  # path to an OLD png; omitted means render the good commit


def create_app(runs_root: Path) -> FastAPI:
    app = FastAPI(title="Visual Bisect")
    runs_root = runs_root.resolve()

    def run_dir(run: str) -> Path:
        d = (runs_root / run).resolve()
        if runs_root not in d.parents and d != runs_root:
            raise HTTPException(400, "bad run id")
        return d

    def read_events(d: Path) -> list[dict]:
        p = d / "events.jsonl"
        out = []
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass  # a half-written last line
        return out

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/runs")
    def list_runs():
        rows = []
        for p in runs_root.rglob("events.jsonl"):
            ev = read_events(p.parent)
            if not ev:
                continue
            start = next((e for e in ev if e["type"] == "run_started"), {})
            end = next((e for e in reversed(ev) if e["type"] in ("run_done", "run_failed")), None)
            rows.append({"id": p.parent.relative_to(runs_root).as_posix(), "focus": start.get("focus"),
                         "judge": start.get("judge"), "model": start.get("model"),
                         "commits": len(start.get("commits", [])), "state": end["type"] if end else "running",
                         "culprit": end.get("culprit_sha") if end else None, "mtime": p.stat().st_mtime})
        return sorted(rows, key=lambda r: -r["mtime"])

    @app.get("/api/events")
    def events(run: str):
        return read_events(run_dir(run))

    @app.get("/api/stream")
    async def stream(run: str):
        d = run_dir(run)

        async def gen():
            sent = 0
            idle = 0
            while True:
                ev = read_events(d)
                for e in ev[sent:]:
                    yield f"data: {json.dumps(e)}\n\n"
                sent = len(ev)
                if ev and ev[-1]["type"] in ("run_done", "run_failed"):
                    return
                idle += 1
                if idle % 15 == 0:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/file")
    def file(run: str, name: str):
        f = (run_dir(run) / name).resolve()
        if run_dir(run) not in f.parents or not f.is_file() or f.suffix.lower() not in (".png", ".diff"):
            raise HTTPException(404)
        return FileResponse(f)

    @app.get("/api/diff")
    def diff(run: str):
        f = run_dir(run) / "culprit.diff"
        if not f.is_file():
            raise HTTPException(404)
        return {"diff": f.read_text(encoding="utf-8", errors="replace")[:20000]}

    @app.post("/api/runs")
    def new_run(body: NewRun):
        repo = Path(body.repo)
        if not (repo / ".git").exists():
            raise HTTPException(400, "repo must be a local git checkout")
        if body.judge not in ("gemma", "pixel-full"):
            raise HTTPException(400, "judge must be gemma or pixel-full from the UI")
        rid = "web/" + time.strftime("%Y%m%d-%H%M%S")
        out = runs_root / rid
        cmd = [sys.executable, "-m", "vbisect.cli", "--repo", str(repo), "--good", body.good, "--bad", body.bad,
               "--focus", body.focus, "--url", body.url, "--judge", body.judge, "--out", str(out)]
        cmd += ["--screenshot", body.screenshot] if body.screenshot else ["--good-render"]
        if body.preset:
            cmd += ["--preset", body.preset]
        if body.model:
            cmd += ["--model", body.model]
        out.mkdir(parents=True, exist_ok=True)
        log = open(out / "cli.log", "w", encoding="utf-8")
        subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        return {"id": rid}

    return app


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--port", type=int, default=8431)
    a = ap.parse_args()
    uvicorn.run(create_app(Path(a.runs)), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
