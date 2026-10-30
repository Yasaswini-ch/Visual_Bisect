"""Builds the web UI into vbisect/web_dist. Used by `vbisect export` and by setup.py (wheel builds).

Stdlib only: setup.py loads this file by path before the package's dependencies exist.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent
DIST = PKG / "web_dist"


def _sources(web: Path) -> list[Path]:
    files = [f for f in (web / "src").rglob("*") if f.is_file()]
    return files + [web / n for n in ("index.html", "package.json", "package-lock.json", "vite.config.ts") if (web / n).is_file()]


def is_stale() -> bool:
    web = ROOT / "web"
    index = DIST / "index.html"
    if not index.is_file():
        return True
    if not (web / "package.json").is_file():  # installed wheel / sdist without sources: use what ships
        return False
    return max(f.stat().st_mtime for f in _sources(web)) > index.stat().st_mtime


def ensure_built() -> Path:
    """Return the compiled frontend directory, building it with npm when missing or older than web/src."""
    if not is_stale():
        return DIST
    web = ROOT / "web"
    npm = shutil.which("npm")
    if not (web / "package.json").is_file() or not npm:
        if (DIST / "index.html").is_file():
            return DIST
        sys.exit("The web UI is not built and npm was not found. Install Node.js, then run "
                 "`npm ci && npm run build` in web/.")
    subprocess.run([npm, "ci"], cwd=web, check=True)  # nosec B603: fixed args, npm resolved by which()
    subprocess.run([npm, "run", "build"], cwd=web, check=True)  # nosec B603
    return DIST
