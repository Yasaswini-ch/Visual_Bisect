"""SSIM baseline judges. Deliberately fair: pixel-crop gets a hand-drawn region."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

TIE = 0.005


def _gray(png: bytes, size: tuple[int, int], region=None) -> np.ndarray:
    img = Image.open(io.BytesIO(png)).convert("L").resize(size)
    if region:
        x, y, w, h = region
        img = img.crop((x, y, x + w, y + h))
    return np.asarray(img)


def judge(old: bytes, new: bytes, cand: bytes, region=None) -> tuple[str, dict]:
    size = Image.open(io.BytesIO(new)).size
    c = _gray(cand, size, region)
    s_old = structural_similarity(_gray(old, size, region), c)
    s_new = structural_similarity(_gray(new, size, region), c)
    detail = {"ssim_old": round(float(s_old), 4), "ssim_new": round(float(s_new), 4)}
    if abs(s_old - s_new) < TIE:
        return "unsure", detail
    return ("old" if s_old > s_new else "new"), detail
