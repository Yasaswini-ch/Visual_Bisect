"""Called by `git bisect run` for each commit. Exit 0=old, 1=new, 125=skip."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import builder, events, judge_gemma, judge_pixel, renderer
from .config import RunConfig

EXIT = {"old": 0, "new": 1}


def current_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def evaluate(cfg: RunConfig, sha: str, wt: Path, cand_png: bytes | None = None) -> tuple[str, dict]:
    """Render (unless cand_png given) and judge. Returns (verdict, details)."""
    run_dir = Path(cfg.run_dir)
    if cand_png is None:
        base = builder.build_and_serve(
            wt, cfg.install_cmd, cfg.build_cmd, cfg.serve_cmd, cfg.build_timeout,
            progress=lambda ph, s: events.append(run_dir, "build_progress", sha=sha, phase=ph, seconds=s))
        img = renderer.screenshot(base + cfg.url, run_dir / "renders" / f"{sha[:10]}.png",
                                  cfg.viewport, cfg.fixed_time, cfg.full_page)
        events.append(run_dir, "render_done", sha=sha, img=f"renders/{sha[:10]}.png")
        cand_png = img.read_bytes()

    old, new = Path(cfg.old_img).read_bytes(), Path(cfg.new_img).read_bytes()
    if cfg.judge == "gemma":
        caller = judge_gemma.make_caller(cfg.model, cfg.focus, cfg.replay)
        verdict, calls = judge_gemma.decide(
            caller, old, new, cand_png,
            on_call=lambda c: events.append(run_dir, "judge_call", sha=sha, **c))
        return verdict, {"api_calls": len(calls)}
    region = cfg.region if cfg.judge == "pixel-crop" else None
    verdict, detail = judge_pixel.judge(old, new, cand_png, region)
    return verdict, detail


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args(argv)
    cfg = RunConfig.load(args.config)
    run_dir = Path(cfg.run_dir)
    sha, verdict, reason = "unknown", "skip", None
    try:
        sha = current_sha()
        events.append(run_dir, "step_started", sha=sha)
        verdict, _ = evaluate(cfg, sha, Path.cwd())
        if verdict == "unsure":
            verdict, reason = "skip", "judge unsure"
    except builder.BuildFailed as e:
        verdict, reason = "skip", f"build failed: {str(e)[:200]}"
    except BaseException as e:  # never let git see an exit code > 127
        verdict, reason = "skip", f"error: {type(e).__name__}: {str(e)[:200]}"
    finally:
        builder.stop_server()
    events.append(run_dir, "step_done", sha=sha, verdict=verdict, skip_reason=reason)
    sys.exit(EXIT.get(verdict, 125))


if __name__ == "__main__":
    main()
