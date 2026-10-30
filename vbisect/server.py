"""Dashboard backend: reads runs/<id>/events.jsonl and serves it to the web UI.

Access control (the server exposes screenshots and diffs of the user's own code):
- Host header must be a loopback name, which stops DNS-rebinding from a hostile web page.
- A browser Origin header, when present, must be a loopback origin.
- Every /api route needs the per-process token, sent as `X-VBisect-Token` or `?token=`
  (EventSource and <img> cannot set headers). The token is injected into index.html, which a
  cross-origin page cannot read, so only a page this server served can call the API.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

TERMINAL = {"run_done", "run_failed"}
LOOPBACK = {"127.0.0.1", "localhost", "::1", "testserver"}
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TOKEN_HEADER = "x-vbisect-token"
TOKEN_META = '<meta name="vb-token" content="{}">'


def frontend_dir() -> Path:
    """Compiled web UI. It lives inside the package so a wheel install finds it."""
    return Path(__file__).resolve().parent / "web_dist"


def read_events(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    if not path.is_file() or path.is_symlink():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            break  # a half-written last line; the next read will have it
        if isinstance(e, dict) and isinstance(e.get("type"), str):
            events.append(e)
    return events


def summarize(run_dir: Path) -> dict | None:
    events = read_events(run_dir)
    start = next((e for e in events if e["type"] == "run_started"), None)
    if start is None or not isinstance(start.get("ts"), (int, float)):
        return None
    end = next((e for e in reversed(events) if e["type"] in TERMINAL), None)
    status = "running" if end is None else ("failed" if end["type"] == "run_failed" else "done")
    return {"id": run_dir.name, "started": start["ts"],
            "date": datetime.fromtimestamp(start["ts"], timezone.utc).isoformat(), "focus": start.get("focus"),
            "judge": start.get("judge"), "commits": len(start.get("commits") or []),
            "status": status, "culprit": end.get("culprit_sha") if end else None,
            "steps": end.get("steps") if end else None, "seconds": end.get("seconds") if end else None}


def _host_ok(host_header: str) -> bool:
    host = host_header.strip()
    host = host[1:host.index("]")] if host.startswith("[") and "]" in host else host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return host in LOOPBACK


def create_app(runs_dir: str | Path = "runs", eval_path: str | Path = "eval/results.json",
               web_dist: str | Path | None = None, token: str | None = None) -> FastAPI:
    runs_root = Path(runs_dir).resolve()
    eval_file = Path(eval_path)
    token = token or secrets.token_urlsafe(24)
    app = FastAPI(title="visual-bisect", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if not _host_ok(request.headers.get("host", "")):
            return PlainTextResponse("forbidden host", status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != "null" and urlsplit(origin).hostname not in LOOPBACK:
            return PlainTextResponse("forbidden origin", status_code=403)
        if request.url.path.startswith("/api/"):
            given = request.headers.get(TOKEN_HEADER) or request.query_params.get("token") or ""
            if not hmac.compare_digest(given.encode(), token.encode()):
                return JSONResponse({"detail": "missing or invalid token"}, status_code=401)
        return await call_next(request)

    def run_path(run_id: str) -> Path:
        if not RUN_ID.match(run_id):
            raise HTTPException(404, "no such run")
        p = (runs_root / run_id).resolve()
        if p.parent != runs_root or not p.is_dir():
            raise HTTPException(404, "no such run")
        return p

    @app.get("/api/runs")
    def list_runs():
        if not runs_root.is_dir():
            return []
        rows = [s for d in runs_root.iterdir() if d.is_dir() and RUN_ID.match(d.name) and (s := summarize(d))]
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

    dist = Path(web_dist) if web_dist else frontend_dir()
    if (dist / "index.html").is_file():
        index_html = (dist / "index.html").read_text(encoding="utf-8")
        page = index_html.replace("</head>", TOKEN_META.format(token) + "</head>", 1)
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            f = (dist / path).resolve()
            if path and dist.resolve() in f.parents and f.is_file() and f.name != "index.html":
                return FileResponse(f)
            return HTMLResponse(page, headers={"Cache-Control": "no-store"})

    return app


def serve(runs_dir: str = "runs", eval_path: str = "eval/results.json",
          host: str = "127.0.0.1", port: int = 8000, token: str | None = None) -> None:
    import uvicorn
    token = token or os.environ.get("VBISECT_TOKEN")  # fixed token for the Vite dev server
    uvicorn.run(create_app(runs_dir, eval_path, token=token), host=host, port=port, log_level="warning")
