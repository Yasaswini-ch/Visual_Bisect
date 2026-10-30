"""vbisect entry point."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

from . import builder, events, git_ops, presets, renderer
from .config import RunConfig


def parse_region(s: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--region needs x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vbisect", description="git bisect that can see.")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--good", required=True)
    ap.add_argument("--bad", default="HEAD")
    ap.add_argument("--screenshot", help="OLD screenshot (PNG)")
    ap.add_argument("--good-render", action="store_true",
                    help="no screenshot: build and render the --good commit as the OLD reference")
    ap.add_argument("--url", default="/", help="page path, e.g. /dashboard")
    ap.add_argument("--focus", required=True, help="what changed, in words")
    ap.add_argument("--preset", choices=sorted(presets.PRESETS), default=None,
                    help=f"command preset (default {presets.DEFAULT}); the flags below override it")
    ap.add_argument("--install-cmd", default=None)
    ap.add_argument("--build-cmd", default=None)
    ap.add_argument("--serve-cmd", default=None, help="use {port} for the port")
    ap.add_argument("--judge", choices=["gemma", "pixel-full", "pixel-crop"], default="gemma")
    ap.add_argument("--region", type=parse_region)
    ap.add_argument("--model", help="vision model; default $GEMMA_MODEL. gemma-*/gemini-* use the Gemini "
                                    "API, ollama:<name> uses a local Ollama server")
    ap.add_argument("--replay", action="store_true", help="use cached model responses only")
    ap.add_argument("--out", help="run folder (default runs/<timestamp>)")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    repo = str(Path(args.repo).resolve())
    shot = Path(args.screenshot) if args.screenshot else None
    if shot is None and not args.good_render:
        sys.exit("give --screenshot OLD.png, or --good-render to render the good commit")
    if shot is not None and (not shot.is_file() or shot.suffix.lower() != ".png"):
        sys.exit(f"--screenshot must be an existing .png: {shot}")
    if args.judge == "pixel-crop" and not args.region:
        sys.exit("--judge pixel-crop needs --region")
    good, bad = git_ops.resolve(repo, args.good), git_ops.resolve(repo, args.bad)
    cmds = presets.resolve(args.preset, args.install_cmd, args.build_cmd, args.serve_cmd)

    run_dir = Path(args.out or Path("runs") / time.strftime("%Y%m%d-%H%M%S")).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").unlink(missing_ok=True)  # a rerun into the same --out must not mix events
    old_img = run_dir / "old.png"
    if shot is not None:
        shutil.copy(shot, old_img)

    cfg = RunConfig(repo=repo, good=good, bad=bad, url=args.url, focus=args.focus,
                    run_dir=str(run_dir), old_img=str(old_img), new_img=str(run_dir / "new.png"),
                    judge=args.judge, model=args.model or os.environ.get("GEMMA_MODEL", ""), region=args.region,
                    install_cmd=cmds.install, build_cmd=cmds.build,
                    serve_cmd=cmds.serve, replay=args.replay)
    if cfg.judge == "gemma" and not cfg.model:
        sys.exit("no model: pass --model or set GEMMA_MODEL (see .env.example)")

    commits = git_ops.commit_list(repo, good, bad)
    events.append(run_dir, "run_started", run_id=run_dir.name, commits=commits, good=good, bad=bad,
                  focus=cfg.focus, url=cfg.url, old_ref_img="old.png", new_ref_img="new.png",
                  judge=cfg.judge, model=cfg.model if cfg.judge == "gemma" else None)
    t0 = time.time()
    wt_new = git_ops.make_worktree(repo, bad)
    wt_old = git_ops.make_worktree(repo, good) if shot is None else None
    wt = None

    def render_ref(worktree: Path, out: str) -> None:
        base = builder.build_and_serve(worktree, cfg.install_cmd, cfg.build_cmd, cfg.serve_cmd)
        try:
            renderer.screenshot(base + cfg.url, Path(out), cfg.viewport, cfg.fixed_time)
        finally:
            builder.stop_server()

    try:
        # NEW reference: render the bad commit once. OLD: the user's screenshot, or the good commit.
        render_ref(wt_new, cfg.new_img)
        if wt_old is not None:
            render_ref(wt_old, cfg.old_img)

        cfg.save()
        wt = git_ops.make_worktree(repo, bad)
        result = git_ops.run_bisect(repo, wt, good, bad, run_dir / "run.json")
    except Exception as e:
        events.append(run_dir, "run_failed", error=str(e))
        raise
    finally:
        builder.stop_server()
        git_ops.cleanup(repo, wt_new)
        if wt_old is not None:
            git_ops.cleanup(repo, wt_old)
        if wt:
            git_ops.cleanup(repo, wt)

    done = events.read_all(run_dir)
    steps = [e for e in done if e["type"] == "step_done"]
    skips = sum(1 for e in steps if e["verdict"] == "skip")
    api_calls = sum(1 for e in done if e["type"] == "judge_call")
    sha = result["culprit"]
    diff_file = None
    if sha:
        info = git_ops.commit_info(repo, sha)
        (run_dir / "culprit.diff").write_text(info["diff"], encoding="utf-8")
        diff_file = "culprit.diff"
        print(f"Culprit: {info['sha'][:10]}  {info['subject']}\n"
              f"Author:  {info['author']}  {info['date']}\n\n{info['stat']}")
    else:
        print("Could not narrow to a single commit. Bisect log tail:\n" + result["log"][-800:])
    events.append(run_dir, "run_done", culprit_sha=sha, steps=len(steps), skips=skips,
                  api_calls=api_calls, seconds=round(time.time() - t0, 1), diff_file=diff_file)
    return 0 if sha else 2


if __name__ == "__main__":
    sys.exit(main())
