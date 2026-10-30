"""Static replay site: `vbisect export --runs runs/ --eval eval/results.json --out site/`.

--runs takes run folders (contain events.jsonl) and/or a parent folder of run folders.
Only the files the dashboard needs are copied, symlinks are never followed, and the output is
built in a staging folder next to --out so a failed export never leaves a half-written site.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from . import frontend_build
from .server import RUN_ID, read_events, summarize

MARKER = ".vbisect-export"
IMAGE_EXT = {".png"}


def discover(paths: list[Path]) -> list[Path]:
    """Expand --runs arguments into run folders. A folder with events.jsonl is a run; otherwise its children are."""
    runs: list[Path] = []
    for p in paths:
        if not p.is_dir():
            sys.exit(f"--runs {p}: not a folder")
        if (p / "events.jsonl").exists():
            runs.append(p.resolve())
        else:
            runs.extend(sorted(c.resolve() for c in p.iterdir() if c.is_dir() and not c.is_symlink()
                               and (c / "events.jsonl").exists()))
    seen: dict[str, Path] = {}
    for r in runs:
        if r.name in seen and seen[r.name] != r:
            sys.exit(f"two runs share the name {r.name!r}: {seen[r.name]} and {r}")
        seen[r.name] = r
    if not seen:
        sys.exit("no runs found: expected folders containing events.jsonl")
    return list(seen.values())


def _safe_file(run: Path, rel: object, exts: set[str] | None) -> Path | None:
    """A regular, non-symlink file strictly inside the run folder, or None."""
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
        return None
    f = run / rel
    try:
        if f.is_symlink() or any(q.is_symlink() for q in f.parents if run in q.parents):
            return None
        f = f.resolve()
    except OSError:
        return None
    if run.resolve() not in f.parents or not f.is_file():
        return None
    if exts is not None and f.suffix.lower() not in exts:
        return None
    return f


def needed_files(run: Path, events: list[dict]) -> tuple[list[str], list[str]]:
    """Relative paths the dashboard reads for this run (from its events), and the ones that are missing."""
    wanted: list[str] = []
    for e in events:
        t = e.get("type")
        if t == "run_started":
            wanted += [e.get("old_ref_img"), e.get("new_ref_img")]
        elif t == "render_done":
            wanted.append(e.get("img"))
        elif t == "run_done":
            wanted.append(e.get("diff_file"))
    ok, missing = [], []
    for rel in dict.fromkeys(w for w in wanted if w):
        (ok if _safe_file(run, rel, None) else missing).append(rel)
    return ok, missing


def copy_run(run: Path, dest: Path) -> list[str]:
    events = read_events(run)
    ok, missing = needed_files(run, events)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    for rel in ok:
        src = _safe_file(run, rel, None)
        assert src is not None
        out = dest / Path(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
    return missing


def load_eval(path: Path | None) -> dict | None:
    if path is None:
        return None
    for p in (path, path.with_name("results.dev.json")):
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                sys.exit(f"{p} is not valid JSON: {e}")
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                sys.exit(f"{p} does not look like results.json (needs a 'results' list)")
            return data
    return None


def export(run_args: list[Path], eval_path: Path | None, out: Path) -> Path:
    out = out.resolve()
    runs = discover(run_args)
    for r in runs:
        if out == r or out in r.parents or r in out.parents:
            sys.exit(f"--out {out} overlaps the run folder {r}; choose a different output folder")
    if out.exists() and (not out.is_dir() or (any(out.iterdir()) and not (out / MARKER).is_file())):
        sys.exit(f"{out} exists and was not created by `vbisect export`; refusing to replace it")

    dist = frontend_build.ensure_built()
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.staging-", dir=out.parent))
    try:
        shutil.copytree(dist, stage, dirs_exist_ok=True, symlinks=False)
        index = []
        for r in runs:
            if not RUN_ID.match(r.name):
                print(f"skipping {r}: folder name has characters the site cannot serve", file=sys.stderr)
                continue
            summary = summarize(r)
            if summary is None:
                print(f"skipping {r}: no valid run_started event in events.jsonl", file=sys.stderr)
                continue
            missing = copy_run(r, stage / "data" / "runs" / r.name)
            for rel in missing:
                print(f"warning: {r.name}: {rel} is missing or not a regular file; the page will show a gap", file=sys.stderr)
            index.append(summary)
        if not index:
            sys.exit("nothing to export: no run had a valid run_started event")
        (stage / "data").mkdir(exist_ok=True)
        (stage / "data" / "index.json").write_text(json.dumps(index), encoding="utf-8")
        data = load_eval(eval_path)
        if data is not None:
            (stage / "data" / "eval.json").write_text(json.dumps(data), encoding="utf-8")
        (stage / ".nojekyll").write_text("")
        (stage / MARKER).write_text("created by vbisect export\n")

        # Swap: move the old export aside first so a failure here still leaves one complete site.
        backup = None
        if out.exists():
            backup = out.with_name(f".{out.name}.old-{stage.name.split('-')[-1]}")
            out.rename(backup)
        try:
            stage.rename(out)
        except OSError:
            if backup is not None:
                backup.rename(out)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(f"Wrote {out} ({len(index)} runs). Preview with: python -m http.server -d {out}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vbisect export", description="Build the static replay site.")
    ap.add_argument("--runs", nargs="+", required=True, type=Path,
                    help="run folders, or a folder that contains run folders (e.g. runs/)")
    ap.add_argument("--eval", type=Path, default=Path("eval/results.json"))
    ap.add_argument("--out", type=Path, default=Path("site"))
    a = ap.parse_args(argv)
    export(a.runs, a.eval, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
