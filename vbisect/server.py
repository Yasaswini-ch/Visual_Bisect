"""Dashboard backend: reads runs/<id>/events.jsonl and serves it to the web UI."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

TERMINAL = {"run_done", "run_failed"}


def read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            break  # a half-written last line; the next read will have it
    return events


def summarize(run_dir: Path) -> dict | None:
    events = read_events(run_dir)
    start = next((e for e in events if e["type"] == "run_started"), None)
    if start is None:
        return None
    end = next((e for e in reversed(events) if e["type"] in TERMINAL), None)
    status = "running" if end is None else ("failed" if end["type"] == "run_failed" else "done")
    return {"id": run_dir.name, "started": start["ts"], "focus": start.get("focus"),
            "judge": start.get("judge"), "commits": len(start.get("commits", [])),
            "status": status, "culprit": end.get("culprit_sha") if end else None,
            "steps": end.get("steps") if end else None, "seconds": end.get("seconds") if end else None}


def create_app(runs_dir: str | Path = "runs", eval_path: str | Path = "eval/results.json",
               web_dist: str | Path | None = None) -> FastAPI:
    runs_root = Path(runs_dir).resolve()
    eval_file = Path(eval_path)
    app = FastAPI(title="visual-bisect")

    def run_path(run_id: str) -> Path:
        p = (runs_root / run_id).resolve()
        if p.parent != runs_root or not p.is_dir():
            raise HTTPException(404, "no such run")
        return p

    @app.get("/api/runs")
    def list_runs():
        if not runs_root.is_dir():
            return []
        rows = [s for d in runs_root.iterdir() if d.is_dir() and (s := summarize(d))]
        return sorted(rows, key=lambda r: r["started"], reverse=True)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return read_events(run_path(run_id))

    @app.get("/api/runs/{run_id}/stream")
    async def stream(run_id: str):
        d = run_path(run_id)

        async def gen():
            sent = 0
            while True:
                events = read_events(d)
                for e in events[sent:]:
                    yield f"data: {json.dumps(e)}\n\n"
                sent = len(events)
                if events and events[-1]["type"] in TERMINAL:
                    return
                await asyncio.sleep(0.4)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs/{run_id}/files/{path:path}")
    def run_file(run_id: str, path: str):
        d = run_path(run_id)
        f = (d / path).resolve()
        if d not in f.parents or not f.is_file():
            raise HTTPException(404, "no such file")
        return FileResponse(f)

    @app.get("/api/eval")
    def get_eval():
        for p in (eval_file, eval_file.with_name("results.dev.json")):
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        raise HTTPException(404, "no eval results yet")

    dist = Path(web_dist) if web_dist else Path(__file__).resolve().parent.parent / "web" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            f = (dist / path).resolve()
            if path and dist in f.parents and f.is_file():
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app


def serve(runs_dir: str = "runs", eval_path: str = "eval/results.json",
          host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(create_app(runs_dir, eval_path), host=host, port=port, log_level="warning")
