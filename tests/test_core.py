import io
import subprocess

import pytest
from PIL import Image

from vbisect import builder, cache, events, git_ops, judge_gemma, judge_pixel, oracle
from vbisect.config import RunConfig


def png(color, size=(200, 100), box=None, box_color=None) -> bytes:
    img = Image.new("RGB", size, color)
    if box:
        img.paste(box_color, box)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def fake_caller(normal1, swapped, normal2=None):
    """Deterministic under threads: pick the response by image order (a == b"a" means normal)."""
    import threading

    lock, normals = threading.Lock(), [normal1] + ([normal2] if normal2 else [])

    def call(a, b, c):
        with lock:
            r = normals.pop(0) if a == b"a" else swapped
        return dict(r)

    return call


R = lambda v, c=0.9: {"verdict": v, "confidence": c, "reason": "x"}


# --- judge_gemma ---------------------------------------------------------

def test_parse_response_variants():
    assert judge_gemma.parse_response('```json\n{"verdict":"old","confidence":0.8,"reason":"r"}\n```')["verdict"] == "old"
    assert judge_gemma.parse_response("no json here") is None
    assert judge_gemma.parse_response('{"verdict":"maybe"}') is None
    assert judge_gemma.parse_response('{"verdict":"new","confidence":"bad"}')["confidence"] == 0.0


def test_decide_agreement_uses_two_calls():
    # swapped call answers in swapped frame: "new" there means OLD overall
    v, calls = judge_gemma.decide(fake_caller(R("old"), R("new")), b"a", b"b", b"c")
    assert v == "old" and len(calls) == 2
    assert [c["order"] for c in calls] == ["normal", "swapped"]


def test_decide_disagreement_tiebreak():
    # call1 old, call2 (swapped) old -> flips to new, call3 old => old wins 2-1
    v, calls = judge_gemma.decide(fake_caller(R("old"), R("old"), R("old")), b"a", b"b", b"c")
    assert v == "old" and len(calls) == 3


def test_decide_low_confidence_is_unsure():
    v, _ = judge_gemma.decide(fake_caller(R("old", 0.3), R("new", 0.3), R("old", 0.3)), b"a", b"b", b"c")
    assert v == "unsure"


def test_decide_swap_maps_back():
    seen = []

    def caller(a, b, c):
        seen.append((a, b))
        return R("old")

    judge_gemma.decide(caller, b"OLD", b"NEW", b"C")
    assert set(seen) == {(b"OLD", b"NEW"), (b"NEW", b"OLD")}


# --- cache ---------------------------------------------------------------

def test_cache_hit_miss_and_replay(tmp_path):
    key = cache.make_key("m", "v1", "focus", [b"1", b"2"])
    assert key != cache.make_key("m", "v2", "focus", [b"1", b"2"])
    assert key != cache.make_key("m", "v1", "focus", [b"2", b"1"])
    with pytest.raises(cache.ReplayMiss):
        cache.cached_call(key, lambda: {"x": 1}, replay=True, cache_dir=tmp_path)
    assert cache.cached_call(key, lambda: {"x": 1}, cache_dir=tmp_path) == {"x": 1}
    assert cache.cached_call(key, lambda: {"x": 2}, replay=True, cache_dir=tmp_path) == {"x": 1}


# --- pixel judge ---------------------------------------------------------

def test_pixel_crop_follows_region():
    old = png("white", box=(0, 0, 50, 100), box_color="blue")
    new = png("white", box=(0, 0, 50, 100), box_color="red")
    cand = png("white", box=(0, 0, 50, 100), box_color="blue")
    assert judge_pixel.judge(old, new, cand, region=(0, 0, 50, 100))[0] == "old"
    assert judge_pixel.judge(old, new, new, region=(0, 0, 50, 100))[0] == "new"


# --- events --------------------------------------------------------------

def test_events_roundtrip_and_validation(tmp_path):
    events.append(tmp_path, "step_started", sha="abc")
    assert events.read_all(tmp_path)[0]["sha"] == "abc"
    with pytest.raises(ValueError):
        events.append(tmp_path, "nope")


# --- oracle exit codes ---------------------------------------------------

def _cfg(tmp_path, judge="pixel-full"):
    (tmp_path / "old.png").write_bytes(png("white"))
    (tmp_path / "new.png").write_bytes(png("black"))
    cfg = RunConfig(repo=".", good="a", bad="b", url="/", focus="f", run_dir=str(tmp_path),
                    old_img=str(tmp_path / "old.png"), new_img=str(tmp_path / "new.png"), judge=judge)
    return cfg, cfg.save()


@pytest.mark.parametrize("cand,code", [(png("white"), 0), (png("black"), 1)])
def test_oracle_exit_codes(tmp_path, monkeypatch, cand, code):
    cfg, path = _cfg(tmp_path)
    real = oracle.evaluate  # real judge, but skip build/render by supplying the candidate
    monkeypatch.setattr(oracle, "current_sha", lambda: "deadbeef")
    monkeypatch.setattr(oracle, "evaluate", lambda c, s, w: real(c, s, w, cand_png=cand))
    with pytest.raises(SystemExit) as e:
        oracle.main(["--config", str(path)])
    assert e.value.code == code


def test_oracle_maps_failures_to_skip(tmp_path, monkeypatch):
    cfg, path = _cfg(tmp_path)
    monkeypatch.setattr(oracle, "current_sha", lambda: "deadbeef")

    def boom(*a, **k):
        raise builder.BuildFailed("nope")

    monkeypatch.setattr(oracle, "evaluate", boom)
    with pytest.raises(SystemExit) as e:
        oracle.main(["--config", str(path)])
    assert e.value.code == 125
    assert events.read_all(tmp_path)[-1]["skip_reason"].startswith("build failed")

    monkeypatch.setattr(oracle, "evaluate", lambda *a, **k: (_ for _ in ()).throw(KeyError("x")))
    with pytest.raises(SystemExit) as e:
        oracle.main(["--config", str(path)])
    assert e.value.code == 125


# --- git ops -------------------------------------------------------------

def test_commit_list_and_info(tmp_path):
    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    for i in range(4):
        (tmp_path / "f.txt").write_text(str(i))
        g("add", ".")
        g("commit", "-q", "-m", f"c{i}")
    commits = git_ops.commit_list(str(tmp_path), "HEAD~3", "HEAD")
    assert [c["subject"] for c in commits] == ["c1", "c2", "c3"]
    info = git_ops.commit_info(str(tmp_path), commits[0]["sha"])
    assert info["subject"] == "c1" and "f.txt" in info["stat"]
