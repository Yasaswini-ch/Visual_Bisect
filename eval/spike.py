"""Judge spike: 5 hand-made (OLD, NEW, candidate) sets run through the real Gemma judge.

Pages are drawn with Pillow so no build/browser is needed. Usage: python eval/spike.py
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from vbisect import judge_gemma

W, H = 1280, 800


def page(sidebar="#1f2a44", pad=16, date="Updated: 12 Jan", badge="3", cards=(12, 48, 7)) -> bytes:
    img = Image.new("RGB", (W, H), "#f4f5f7")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 60), fill="#ffffff")
    d.text((300, 25), f"Dashboard   {date}", fill="#111")
    d.rectangle((0, 60, 220, H), fill=sidebar)
    for i, name in enumerate(["Home", "Reports", "Users", "Billing", "Settings"]):
        y = 80 + i * (28 + pad)
        d.text((24, y), name, fill="#fff")
    d.ellipse((180, 80 + 2 * (28 + pad), 200, 100 + 2 * (28 + pad)), fill="#e53935")
    d.text((186, 84 + 2 * (28 + pad)), badge, fill="#fff")
    for i, n in enumerate(cards):
        x = 260 + i * 330
        d.rectangle((x, 100, x + 300, 260), fill="#fff", outline="#ccc")
        d.text((x + 20, 160), str(n), fill="#111")
    d.rectangle((0, H - 40, W, H), fill="#222")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


OLD = page()
SETS = [
    # (name, focus, new, candidate, expected)
    ("sidebar-color/obvious-old", "the left sidebar background color", page(sidebar="#c62828"), page(date="Updated: 3 Feb"), "old"),
    ("sidebar-color/obvious-new", "the left sidebar background color", page(sidebar="#c62828"), page(sidebar="#c62828", cards=(1, 2, 3)), "new"),
    ("padding/subtle-new", "the vertical spacing between sidebar nav items", page(pad=20), page(pad=20, date="Updated: 9 Mar"), "new"),
    ("date-only/old", "the left sidebar background color", page(sidebar="#c62828"), page(date="Updated: 30 Oct", cards=(99, 1, 5)), "old"),
    ("hard-noise/old", "the left sidebar background color", page(sidebar="#c62828", badge="9"), page(badge="7"), "old"),
]


def main() -> int:
    model = os.environ.get("GEMMA_MODEL")
    if not model or not os.environ.get("GEMINI_API_KEY"):
        sys.exit("set GEMINI_API_KEY and GEMMA_MODEL (see .env.example)")
    correct = 0
    for name, focus, new, cand, expected in SETS:
        caller = judge_gemma.make_gemini_caller(model, focus)
        verdict, calls = judge_gemma.decide(caller, OLD, new, cand)
        ok = verdict == expected
        correct += ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:28} got={verdict:6} expected={expected}  calls={len(calls)}")
        for c in calls:
            print(f"      [{c['order']:7}] {c['verdict']:6} {c['confidence']:.2f}  {c['reason']}")
    print(f"\n{correct}/{len(SETS)} correct (gate: >= 4)")
    return 0 if correct >= 4 else 1


if __name__ == "__main__":
    sys.exit(main())
