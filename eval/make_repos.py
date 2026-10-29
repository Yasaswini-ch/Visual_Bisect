"""Generate synthetic git repos with a known culprit commit.

Each commit rewrites the app files from a `state` dict, so history is a real git log of
real diffs. Noise commits change things outside the focus (the left sidebar's look);
exactly one culprit commit changes it. truth.json records the answer.

Usage: python eval/make_repos.py --out eval/cases --seeds 1 2 3 [--commits 100]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import shutil
import stat
import subprocess
from pathlib import Path

BASE = Path(__file__).parent / "base_app"
FOCUS = "the left sidebar (its color, width, icons, item order, text and spacing)"

NAV = [("🏠", "Home"), ("📊", "Reports"), ("👥", "Users"), ("💳", "Billing"),
       ("🔔", "Alerts"), ("⚙️", "Settings"), ("❓", "Help")]

INITIAL = {
    "date": "12 Jan", "subtitle": "Overview of the week", "cards": [12, 48, 7, 31],
    "footer": "#222222", "spacing": 24, "badge": 3, "noop": 0,
    "sidebar": {"color": "#1f2a44", "width": 220, "pad": 14, "weight": 400, "size": 15,
                "items": list(range(6)), "truncate": False},
}

CULPRITS = {
    "color": ("obvious", lambda s, r: s["sidebar"].update(color=r.choice(["#c62828", "#2e7d32", "#6a1b9a"]))),
    "width": ("obvious", lambda s, r: s["sidebar"].update(width=r.choice([150, 300]))),
    "icon-removed": ("obvious", lambda s, r: s["sidebar"].update(items=[i for i in s["sidebar"]["items"] if i != 3])),
    "reorder": ("obvious", lambda s, r: s["sidebar"].update(items=list(reversed(s["sidebar"]["items"])))),
    "font-weight": ("subtle", lambda s, r: s["sidebar"].update(weight=700)),
    "padding-16": ("obvious", lambda s, r: s["sidebar"].update(pad=s["sidebar"]["pad"] + 16)),
    "padding-4": ("subtle", lambda s, r: s["sidebar"].update(pad=s["sidebar"]["pad"] + 4)),
    "truncate": ("subtle", lambda s, r: s["sidebar"].update(truncate=True)),
}


def noise(state: dict, r: random.Random) -> str:
    kind = r.choice(["date", "numbers", "subtitle", "cards", "footer", "spacing", "noop", "noop", "badge"])
    if kind == "date":
        state["date"] = f"{r.randint(1, 28)} {r.choice(['Jan', 'Feb', 'Mar', 'Apr'])}"
    elif kind == "numbers":
        state["cards"] = [r.randint(1, 99) for _ in state["cards"]]
    elif kind == "subtitle":
        state["subtitle"] = r.choice(["Overview of the week", "Your numbers", "Weekly summary", "At a glance"])
    elif kind == "cards":
        n = max(3, min(6, len(state["cards"]) + r.choice([-1, 1])))
        state["cards"] = (state["cards"] + [r.randint(1, 99) for _ in range(6)])[:n]
    elif kind == "footer":
        state["footer"] = r.choice(["#222222", "#333344", "#1a1a1a"])
    elif kind == "spacing":
        state["spacing"] = r.choice([16, 24, 32])
    elif kind == "badge":
        state["badge"] = r.randint(1, 99)  # hard noise: changes inside the sidebar, not its look
    else:
        state["noop"] += 1
    return kind


def render(state: dict) -> dict[str, str]:
    sb = state["sidebar"]
    items = [NAV[i] for i in sb["items"]]
    nav = "\n".join(
        f'      <li><span class="icon">{ic}</span><span class="label">{label}</span>'
        + (f'<span class="badge">{state["badge"]}</span>' if label == "Alerts" else "") + "</li>"
        for ic, label in items)
    cards = "\n".join(f'      <div class="card"><h3>Metric {i + 1}</h3><p>{n}</p></div>'
                      for i, n in enumerate(state["cards"]))
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Dashboard</title>
<link rel="stylesheet" href="/src/styles.css"></head>
<body>
  <header><h1>Dashboard</h1><span>{state["subtitle"]} · Updated: {state["date"]}</span></header>
  <div class="layout">
    <aside><ul>
{nav}
    </ul></aside>
    <main>
{cards}
    </main>
  </div>
  <footer>© Acme</footer>
  <script type="module" src="/src/main.ts"></script>
</body></html>
"""
    ellipsis = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:60px;" if sb["truncate"] else ""
    css = f"""/* noop {state["noop"]} */
body {{ margin:0; font-family: Arial, sans-serif; background:#f4f5f7; }}
header {{ height:60px; background:#fff; display:flex; align-items:center; gap:16px; padding:0 24px; }}
.layout {{ display:flex; min-height:700px; }}
aside {{ width:{sb["width"]}px; background:{sb["color"]}; color:#fff; }}
aside ul {{ list-style:none; margin:0; padding:16px; }}
aside li {{ display:flex; align-items:center; gap:10px; padding:{sb["pad"]}px 0;
  font-weight:{sb["weight"]}; font-size:{sb["size"]}px; }}
aside .label {{ {ellipsis} }}
.badge {{ background:#e53935; border-radius:10px; padding:1px 7px; font-size:12px; }}
main {{ flex:1; display:flex; flex-wrap:wrap; gap:{state["spacing"]}px; padding:{state["spacing"]}px; align-content:flex-start; }}
.card {{ background:#fff; border:1px solid #ccc; padding:16px; width:200px; }}
footer {{ background:{state["footer"]}; color:#fff; padding:12px 24px; }}
"""
    return {"index.html": html, "src/styles.css": css, "src/main.ts": f"// app entry {state['noop']}\nexport {{}};\n"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def make_repo(out: Path, seed: int, commits: int = 100, culprit_type: str | None = None) -> dict:
    r = random.Random(seed)
    repo = out / f"seed{seed}"
    if repo.exists():
        def _force(func, path, _exc):  # git objects are read-only on Windows
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(repo, onerror=_force)
    (repo / "src").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "eval@example.com")
    git(repo, "config", "user.name", "Eval")
    for f in ("package.json", "package-lock.json"):
        shutil.copy(BASE / f, repo / f)
    (repo / ".gitignore").write_text("node_modules\ndist\n")

    culprit_idx = r.randint(min(10, commits // 3), min(90, commits - commits // 3))
    ctype = culprit_type or r.choice(sorted(CULPRITS))
    difficulty, mutate = CULPRITS[ctype]
    state = copy.deepcopy(INITIAL)
    culprit_sha = None
    for i in range(commits):
        if i == culprit_idx:
            mutate(state, r)
            msg = r.choice(["chore: tidy imports", "refactor: simplify layout code", "style: cleanup"])
        else:
            msg = f"{noise(state, r)}: update {i}"
        for name, text in render(state).items():
            (repo / name).write_text(text, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", msg)
        if i == culprit_idx:
            culprit_sha = git(repo, "rev-parse", "HEAD")
    truth = {"seed": seed, "culprit_sha": culprit_sha, "culprit_index": culprit_idx,
             "commits": commits, "culprit_type": ctype, "difficulty": difficulty, "focus": FOCUS,
             "good": git(repo, "rev-list", "--max-parents=0", "HEAD"), "bad": "HEAD"}
    (repo / ".." / f"seed{seed}.truth.json").resolve().write_text(json.dumps(truth, indent=2))
    return truth


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="eval/cases")
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--commits", type=int, default=100)
    ap.add_argument("--type", choices=sorted(CULPRITS))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for s in a.seeds:
        t = make_repo(out, s, a.commits, a.type)
        print(f"seed {s}: culprit #{t['culprit_index']} {t['culprit_type']} {t['culprit_sha'][:10]}")


if __name__ == "__main__":
    main()
