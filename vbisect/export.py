"""Static replay site: `vbisect export --runs runs/demo runs/real-case --eval eval/results.json --out site/`."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .server import summarize

ROOT = Path(__file__).resolve().parent.parent


def build_web() -> Path:
    web = ROOT / "web"
    dist = web / "dist"
    src_files = [f for f in (web / "src").rglob("*") if f.is_file()] + [web / "index.html", web / "package.json"]
    stale = dist.is_dir() and max(f.stat().st_mtime for f in src_files) > (dist / "index.html").stat().st_mtime
    if not dist.is_dir() or stale:
        npm = shutil.which("npm")
        if not npm:
            sys.exit("web/dist is missing and npm was not found; run `npm ci && npm run build` in web/")
        subprocess.run([npm, "ci"], cwd=web, check=True)  # nosec: fixed args, npm resolved by which()
        subprocess.run([npm, "run", "build"], cwd=web, check=True)  # nosec: fixed args
    return dist


def _no_symlinks(directory: str, names: list[str]) -> list[str]:
    return [n for n in names if (Path(directory) / n).is_symlink()]


def export(runs: list[Path], eval_path: Path | None, out: Path) -> None:
    out = out.resolve()
    for r in runs:
        r = r.resolve()
        if out == r or out in r.parents or r in out.parents:
            sys.exit(f"--out {out} overlaps the run folder {r}; choose a different output folder")
    if out.exists() and any(out.iterdir()) and not (out / "data" / "index.json").is_file():
        sys.exit(f"{out} exists and is not a previous export; refusing to delete it")
    dist = build_web()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(dist, out)
    data = out / "data"
    index = []
    for r in runs:
        s = summarize(r)
        if s is None:
            sys.exit(f"{r} has no run_started event")
        shutil.copytree(r, data / "runs" / r.name, ignore=_no_symlinks)
        index.append(s)
    data.mkdir(parents=True, exist_ok=True)
    (data / "index.json").write_text(json.dumps(index), encoding="utf-8")
    if eval_path and eval_path.is_file():
        shutil.copy(eval_path, data / "eval.json")
    (out / ".nojekyll").write_text("")
    print(f"Wrote {out} ({len(index)} runs). Serve with: python -m http.server -d {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vbisect export", description="Build the static replay site.")
    ap.add_argument("--runs", nargs="+", required=True, type=Path)
    ap.add_argument("--eval", type=Path, default=Path("eval/results.json"))
    ap.add_argument("--out", type=Path, default=Path("site"))
    a = ap.parse_args(argv)
    export(a.runs, a.eval, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
