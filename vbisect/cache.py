"""Response cache keyed by input hashes; powers --replay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "vbisect" / "responses"


class ReplayMiss(RuntimeError):
    pass


def make_key(model: str, prompt_version: str, focus: str, images: list[bytes]) -> str:
    h = hashlib.sha256()
    for part in (model, prompt_version, focus):
        h.update(part.encode())
        h.update(b"\0")
    for img in images:
        h.update(hashlib.sha256(img).digest())
    return h.hexdigest()


def get(key: str, cache_dir: Path = CACHE_DIR) -> dict | None:
    p = cache_dir / f"{key}.json"
    return json.loads(p.read_text()) if p.exists() else None


def put(key: str, value: dict, cache_dir: Path = CACHE_DIR) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(value))


def cached_call(key: str, fn, replay: bool = False, cache_dir: Path = CACHE_DIR) -> dict:
    hit = get(key, cache_dir)
    if hit is not None:
        return hit
    if replay:
        raise ReplayMiss(f"--replay: no cached response for {key[:12]}")
    value = fn()
    put(key, value, cache_dir)
    return value
