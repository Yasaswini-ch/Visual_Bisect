"""Append-only event log: the single source of truth for live view and replay."""
from __future__ import annotations

import json
import time
from pathlib import Path

EVENT_TYPES = {
    "run_started", "step_started", "build_progress", "render_done",
    "judge_call", "step_done", "run_done", "run_failed",
}


def append(run_dir: str | Path, type_: str, **fields) -> None:
    if type_ not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {type_}")
    path = Path(run_dir) / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": time.time(), "type": type_, **fields})
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def read_all(run_dir: str | Path) -> list[dict]:
    path = Path(run_dir) / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
