"""Run every case with each judge and write eval/results.json.

Usage: python eval/run_eval.py --cases eval/cases --seeds 101 102 ... --judges gemma pixel-crop pixel-full
                               [--repeats 3] [--workers 3] [--out eval/results.json] [--label test]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SIDEBAR_REGION = "0,60,300,740"  # widest sidebar the generator can produce
MODEL = ""  # set from --model; empty means use $GEMMA_MODEL


def run_case(cases: Path, seed: int, judge: str, rep: int, runs_root: Path) -> dict:
    repo = cases / f"seed{seed}"
    truth = json.loads((cases / f"seed{seed}.truth.json").read_text())
    out = runs_root / judge / f"seed{seed}-r{rep}"
    cmd = [sys.executable, "-m", "vbisect.cli", "--repo", str(repo), "--good", truth["good"],
           "--bad", "HEAD", "--good-render", "--focus", truth["focus"], "--judge", judge,
           "--out", str(out)]
    if judge == "pixel-crop":
        cmd += ["--region", SIDEBAR_REGION]
    if judge == "gemma" and MODEL:
        cmd += ["--model", MODEL]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out.mkdir(parents=True, exist_ok=True)
    (out / "cli.log").write_text(f"returncode={p.returncode}\n--- stdout\n{p.stdout}\n--- stderr\n{p.stderr}",
                                 encoding="utf-8")
    return {"seed": seed, "judge": judge, "rep": rep, **score(out, truth), "returncode": p.returncode}


def score(out: Path, truth: dict) -> dict:
    path = out / "events.jsonl"
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    started = next((e for e in events if e["type"] == "run_started"), None)
    done = next((e for e in events if e["type"] == "run_done"), None)
    res = {"culprit_type": truth["culprit_type"], "difficulty": truth["difficulty"],
           "found": done["culprit_sha"] if done else None, "exact": False,
           "steps": 0, "skips": 0, "api_calls": 0, "seconds": None,
           "step_correct": 0, "step_judged": 0, "run": str(out)}
    if done:
        res.update(exact=done["culprit_sha"] == truth["culprit_sha"], steps=done["steps"],
                   skips=done["skips"], api_calls=done["api_calls"], seconds=done["seconds"])
    if started:
        order = {c["sha"]: i for i, c in enumerate(started["commits"])}
        for e in events:
            if e["type"] == "step_done" and e["verdict"] in ("old", "new") and e["sha"] in order:
                # commits before the culprit index look OLD; the culprit and later look NEW
                # (rev-list excludes the root commit, so list index i is repo commit i+1)
                actual = "new" if order[e["sha"]] + 1 >= truth["culprit_index"] else "old"
                res["step_judged"] += 1
                res["step_correct"] += e["verdict"] == actual
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="eval/cases")
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--judges", nargs="+", default=["gemma", "pixel-crop", "pixel-full"])
    ap.add_argument("--repeats", type=int, default=1, help="repeats for the gemma judge")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--model", default="", help="vision model for the gemma judge (default $GEMMA_MODEL)")
    ap.add_argument("--label", default="dev")
    ap.add_argument("--out", default="eval/results.json")
    a = ap.parse_args()
    global MODEL
    MODEL = a.model
    cases, runs_root = Path(a.cases), Path("runs") / "eval" / a.label

    jobs = [(s, j, r) for s in a.seeds for j in a.judges
            for r in range(a.repeats if j == "gemma" else 1)]
    gemma_slot = threading.Semaphore(1)  # concurrent model requests overloaded the API (500/504s)

    def safe(job):
        # one crashing job must not lose the rest of a multi-hour batch
        try:
            if job[1] == "gemma":
                with gemma_slot:
                    res = run_case(cases, *job, runs_root)
            else:
                res = run_case(cases, *job, runs_root)
        except Exception as e:
            s, j, r = job
            res = {"seed": s, "judge": j, "rep": r, "exact": False, "found": None, "steps": 0, "skips": 0,
                   "api_calls": 0, "seconds": None, "step_correct": 0, "step_judged": 0,
                   "culprit_type": "unknown", "difficulty": "unknown", "error": repr(e)}
        print(f"done seed{res['seed']} {res['judge']} r{res['rep']} exact={res['exact']} "
              f"steps={res['steps']} skips={res['skips']}", flush=True)
        return res

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(safe, jobs))
    Path(a.out).write_text(json.dumps({"label": a.label, "results": results}, indent=2))
    ok = sum(r["exact"] for r in results)
    print(f"wrote {a.out}: {ok}/{len(results)} exact")


if __name__ == "__main__":
    main()
