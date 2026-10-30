"""Install/build/serve command presets so common web projects work without extra flags."""
from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    install: str
    build: str
    serve: str  # {port} is filled in by the builder


PRESETS: dict[str, Preset] = {
    "vite": Preset("npm ci", "npm run build",
                   "npx vite preview --host 127.0.0.1 --strictPort --port {port}"),
    "next": Preset("npm ci", "npm run build", "npx next start -H 127.0.0.1 -p {port}"),
    # Plain HTML/CSS/JS: nothing to install or build, just serve the checked-out folder.
    "static": Preset("", "", f'"{sys.executable}" -m http.server {{port}} --bind 127.0.0.1'),
}

DEFAULT = "vite"


def resolve(name: str | None, install: str | None, build: str | None, serve: str | None) -> Preset:
    """Explicit command flags override the preset's values."""
    base = PRESETS[name or DEFAULT]
    return Preset(base.install if install is None else install,
                  base.build if build is None else build,
                  base.serve if serve is None else serve)
