"""Gemma judge: 3-image comparison, order swap, tie-break, skip when unsure."""
from __future__ import annotations

import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from . import cache

PROMPT_VERSION = "judge_v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt"
MIN_CONF = 0.6
MAX_SIDE = 1600

# A "caller" takes (old_png, new_png, cand_png) in A/B/C order and returns a parsed
# {"verdict","confidence","reason"} dict. Injected so the decision logic is testable.
Caller = Callable[[bytes, bytes, bytes], dict]


def parse_response(text: str) -> dict | None:
    """Parse the model's JSON, tolerating code fences and surrounding prose."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if d.get("verdict") not in ("old", "new", "unsure"):
        return None
    try:
        d["confidence"] = float(d.get("confidence", 0))
    except (TypeError, ValueError):
        d["confidence"] = 0.0
    d.setdefault("reason", "")
    return d


def downscale(png: bytes, max_side: int = MAX_SIDE) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(png))
    if max(img.size) <= max_side:
        return png
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _flip(verdict: str) -> str:
    return {"old": "new", "new": "old"}.get(verdict, verdict)


def decide(call: Caller, old: bytes, new: bytes, cand: bytes, on_call=None) -> tuple[str, list[dict]]:
    """Return (verdict, calls). verdict is 'old' | 'new' | 'unsure'.

    Call 1 normal order, call 2 swapped (verdict mapped back). Agreement with both
    confidences >= MIN_CONF wins; otherwise a third normal-order call breaks the tie.
    """
    calls: list[dict] = []

    def run(order: str, call_no: int) -> dict:
        t0 = time.time()
        if order == "normal":
            r = dict(call(old, new, cand))
        else:
            r = dict(call(new, old, cand))
            r["verdict"] = _flip(r["verdict"])
        r.update(order=order, call_no=call_no, seconds=round(time.time() - t0, 2))
        calls.append(r)
        if on_call:
            on_call(r)
        return r

    # The two first calls are independent, so run them concurrently (API latency dominates).
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa, fb = pool.submit(run, "normal", 1), pool.submit(run, "swapped", 2)
        a, b = fa.result(), fb.result()
    if a["verdict"] == b["verdict"] and a["verdict"] != "unsure" \
            and min(a["confidence"], b["confidence"]) >= MIN_CONF:
        return a["verdict"], calls

    c = run("normal", 3)
    votes = [x["verdict"] for x in (a, b, c)]
    for v in ("old", "new"):
        if votes.count(v) >= 2:
            confs = [x["confidence"] for x in (a, b, c) if x["verdict"] == v]
            if sum(confs) / len(confs) >= MIN_CONF:
                return v, calls
    return "unsure", calls


def make_gemini_caller(model: str, focus: str, replay: bool = False) -> Caller:
    """Real caller using google-genai. Caches every response by input hash."""
    prompt = PROMPT_PATH.read_text().format(focus=focus)
    client = None

    def call(old: bytes, new: bytes, cand: bytes) -> dict:
        nonlocal client
        imgs = [downscale(i) for i in (old, new, cand)]
        key = cache.make_key(model, PROMPT_VERSION, focus, imgs)

        def fetch() -> dict:
            nonlocal client
            from google import genai
            from google.genai import types

            if client is None:
                # hung calls (seen up to 345 s) are cheaper to retry than to wait out
                client = genai.Client(http_options=types.HttpOptions(timeout=120_000))
            contents = [prompt]
            for label, img in zip(("Image A (OLD):", "Image B (NEW):", "Image C (CANDIDATE):"), imgs):
                contents += [label, types.Part.from_bytes(data=img, mime_type="image/png")]
            cfg = types.GenerateContentConfig(temperature=0)
            last_err: Exception | None = None
            for attempt in range(5):  # 500s from the API are usually transient
                try:
                    resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                    parsed = parse_response(resp.text or "")
                    if parsed is None:
                        resp = client.models.generate_content(
                            model=model, contents=contents + ["Reply with JSON only."], config=cfg)
                        parsed = parse_response(resp.text or "")
                    if parsed is None:
                        return {"verdict": "unsure", "confidence": 0.0, "reason": "unparseable response"}
                    return parsed
                except Exception as e:  # network / rate limit
                    last_err = e
                    time.sleep(2 * 2 ** attempt)
            raise RuntimeError(f"Gemini API failed after retries: {last_err}")

        return cache.cached_call(key, fetch, replay=replay)

    return call
