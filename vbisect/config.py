"""Run configuration shared between the CLI and the oracle subprocess."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunConfig:
    repo: str
    good: str
    bad: str
    url: str
    focus: str
    run_dir: str
    old_img: str = ""
    new_img: str = ""
    judge: str = "gemma"  # gemma | pixel-full | pixel-crop
    model: str = ""
    region: tuple[int, int, int, int] | None = None  # x, y, w, h
    install_cmd: str = "npm ci"
    build_cmd: str = "npm run build"
    serve_cmd: str = "npx vite preview --host 127.0.0.1 --strictPort --port {port}"
    build_timeout: int = 120
    viewport: tuple[int, int] = (1280, 800)
    fixed_time: str = "2026-01-15T12:00:00Z"
    full_page: bool = False
    replay: bool = False
    max_skips: int = 5
    extra: dict = field(default_factory=dict)

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path or Path(self.run_dir) / "run.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))
        return path

    @classmethod
    def load(cls, path: str | Path) -> "RunConfig":
        data = json.loads(Path(path).read_text())
        if data.get("region"):
            data["region"] = tuple(data["region"])
        data["viewport"] = tuple(data["viewport"])
        return cls(**data)
