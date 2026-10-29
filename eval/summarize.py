"""results.json -> markdown tables. Usage: python eval/summarize.py [eval/results.json]"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from statistics import mean

NAMES = {"gemma": "Gemma 4", "pixel-crop": "Pixel-crop", "pixel-full": "Pixel-full"}


def per_repeat_exact(rows: list[dict]) -> list[int]:
    by_rep = defaultdict(int)
    for r in rows:
        by_rep[r["rep"]] += r["exact"]
    return [by_rep[k] for k in sorted(by_rep)]


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "eval/results.json"
    data = json.load(open(path))
    rows = data["results"]
    seeds = len({r["seed"] for r in rows})
    by_judge = defaultdict(list)
    for r in rows:
        by_judge[r["judge"]].append(r)

    print(f"Results ({data['label']} set, {seeds} repos)\n")
    print("| Judge | Exact culprit found | Per-step accuracy | Avg steps | Avg skips | Avg time |")
    print("|---|---|---|---|---|---|")
    for j, rs in by_judge.items():
        reps = per_repeat_exact(rs)
        exact = f"{mean(reps):.1f}/{seeds}" + (f" (range {min(reps)}–{max(reps)})" if len(reps) > 1 else "")
        judged = sum(r["step_judged"] for r in rs)
        acc = f"{100 * sum(r['step_correct'] for r in rs) / judged:.0f}%" if judged else "n/a"
        times = [r["seconds"] for r in rs if r["seconds"] is not None]
        print(f"| {NAMES.get(j, j)} | {exact} | {acc} | {mean(r['steps'] for r in rs):.1f} | "
              f"{mean(r['skips'] for r in rs):.1f} | {mean(times):.0f} s |" if times else
              f"| {NAMES.get(j, j)} | {exact} | {acc} | - | - | - |")

    print("\nExact-culprit rate by culprit type\n")
    types = sorted({r["culprit_type"] for r in rows})
    print("| Culprit type | " + " | ".join(NAMES.get(j, j) for j in by_judge) + " |")
    print("|---|" + "---|" * len(by_judge))
    for t in types:
        cells = []
        for rs in by_judge.values():
            sub = [r for r in rs if r["culprit_type"] == t]
            cells.append(f"{sum(r['exact'] for r in sub)}/{len(sub)}")
        print(f"| {t} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
