"""Write a synthetic but realistic run folder to develop the dashboard against.
Usage: python web/make_sample_run.py [runs/sample]"""
import json, random, sys, time
from pathlib import Path
from PIL import Image, ImageDraw

out = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/sample")
(out / "renders").mkdir(parents=True, exist_ok=True)
rnd = random.Random(7)
N, CULPRIT = 16, 10
subjects = ["Bump deps", "Refactor nav", "Add footer links", "Fix typo in pricing", "Tidy tests", "Update README",
            "Add card shadows", "Rename util", "Lazy-load charts", "Tweak spacing tokens", "Unify button styles",
            "Add dark-mode flag", "Cache API calls", "Fix lint", "Update copy", "Polish header"]
shas = ["%040x" % rnd.getrandbits(160) for _ in range(N)]
commits = [{"sha": s, "subject": subjects[i], "date": f"2026-10-{10 + i // 2:02d}T1{i % 10}:00:00+00:00",
            "author": ["Ada", "Linus", "Grace"][i % 3]} for i, s in enumerate(shas)]
commits[CULPRIT]["subject"] = "Unify button styles"

def render(path, new):
    im = Image.new("RGB", (1280, 720), (248, 249, 251)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1280, 64], fill=(24, 30, 46)); d.text((32, 24), "Acme Dashboard", fill="white")
    for i in range(3):
        x = 48 + i * 400
        d.rounded_rectangle([x, 120, x + 360, 300], 14 if new else 4, fill="white", outline=(220, 224, 232))
        d.text((x + 24, 150), ["Revenue", "Users", "Churn"][i], fill=(90, 98, 120))
        d.text((x + 24, 190), ["$48,210", "12,904", "2.1%"][i], fill=(20, 24, 40))
    d.rounded_rectangle([48, 360, 260, 416], 28 if new else 6, fill=(220, 60, 60) if new else (37, 99, 235))
    d.text((120, 382), "Upgrade", fill="white")
    im.save(path)

render(out / "old.png", False); render(out / "new.png", True)
for i, s in enumerate(shas):
    render(out / "renders" / f"{s[:10]}.png", i >= CULPRIT)
(out / "culprit.diff").write_text(f"""diff --git a/src/Button.css b/src/Button.css
index 3f2a1c0..9b7d4e2 100644
--- a/src/Button.css
+++ b/src/Button.css
@@ -1,8 +1,8 @@
 .btn {{
-  background: #2563eb;
-  border-radius: 6px;
+  background: #dc3c3c;
+  border-radius: 28px;
   color: white;
   padding: 12px 32px;
 }}
diff --git a/src/Card.css b/src/Card.css
index 1a2b3c4..5d6e7f8 100644
--- a/src/Card.css
+++ b/src/Card.css
@@ -1,4 +1,4 @@
 .card {{
-  border-radius: 4px;
+  border-radius: 14px;
 }}
""")

t = time.time() - 120
ev = []
def add(type_, dt, **f):
    global t; t += dt; ev.append({"ts": round(t, 3), "type": type_, **f})
add("run_started", 0, run_id=out.name, commits=commits, good="0" * 40, bad=shas[-1],
    focus="The Upgrade button and the cards got rounder and the button turned red", url="/",
    old_ref_img="old.png", new_ref_img="new.png", judge="gemma")
lo, hi, step, call = -1, N - 1, 0, 0   # lo = last OLD index, hi = first known NEW index
skip_at = 5
while hi - lo > 1:
    mid = (lo + hi) // 2
    step += 1; sha = shas[mid]
    add("step_started", 0.4, sha=sha, step_no=step, est_total=4)
    add("build_progress", 0.3, sha=sha, phase="install-cached", seconds=0.6)
    if mid == skip_at:
        add("build_progress", 2.5, sha=sha, phase="build", seconds=2.4)
        add("step_done", 0.2, sha=sha, verdict="skip", skip_reason="build failed")
        lo = lo  # treat skip: git picks a neighbour next
        skip_at = -1
        mid = mid + 1; step += 1; sha = shas[mid]
        add("step_started", 0.4, sha=sha, step_no=step, est_total=4)
    add("build_progress", 0.3, sha=sha, phase="install-cached", seconds=0.5)
    add("build_progress", 4.0, sha=sha, phase="build", seconds=3.9)
    add("build_progress", 1.0, sha=sha, phase="serve", seconds=0.9)
    add("render_done", 1.2, sha=sha, img=f"renders/{sha[:10]}.png")
    is_new = mid >= CULPRIT; v = "new" if is_new else "old"
    reason = ("Candidate has the red pill-shaped Upgrade button and rounded cards, matching NEW." if is_new else
              "Candidate still has the blue squarish Upgrade button and sharp cards, matching OLD.")
    for order in ("normal", "swapped"):
        call += 1
        add("judge_call", 2.1, sha=sha, call_no=call, order=order, verdict=v,
            confidence=round(rnd.uniform(.82, .97), 2), reason=reason, seconds=2.0)
    add("step_done", 0.1, sha=sha, verdict=v, skip_reason=None)
    if is_new: hi = mid
    else: lo = mid
add("run_done", 0.5, culprit_sha=shas[hi], steps=step, skips=1, api_calls=call,
    seconds=round(t - ev[0]["ts"], 1), diff_file="culprit.diff")
(out / "events.jsonl").write_text("\n".join(json.dumps(e) for e in ev) + "\n")
print("wrote", out, len(ev), "events; culprit", shas[hi][:10])
