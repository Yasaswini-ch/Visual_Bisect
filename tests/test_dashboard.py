"""Dashboard backend: server access control and routes, SSE, and the static export."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vbisect import export as export_mod
from vbisect import frontend_build
from vbisect.server import create_app, read_events, summarize

TOKEN = "t0ken"
AUTH = {"X-VBisect-Token": TOKEN}


def make_run(root: Path, name: str = "r1", *, finished: bool = True, render: bool = True) -> Path:
    d = root / name
    (d / "renders").mkdir(parents=True)
    commits = [{"sha": f"{i:040x}", "subject": f"c{i}", "date": "2026-10-01T00:00:00+00:00", "author": "a"} for i in range(4)]
    ev = [
        {"ts": 100.0, "type": "run_started", "run_id": name, "commits": commits, "good": "g", "bad": commits[-1]["sha"],
         "focus": "the button", "url": "/", "old_ref_img": "old.png", "new_ref_img": "new.png", "judge": "pixel-full"},
        {"ts": 101.0, "type": "step_started", "sha": commits[1]["sha"]},
        {"ts": 102.0, "type": "render_done", "sha": commits[1]["sha"], "img": f"renders/{commits[1]['sha'][:10]}.png"},
        {"ts": 103.0, "type": "step_done", "sha": commits[1]["sha"], "verdict": "new", "skip_reason": None},
    ]
    if finished:
        ev.append({"ts": 104.0, "type": "run_done", "culprit_sha": commits[1]["sha"], "steps": 1, "skips": 0,
                   "api_calls": 0, "seconds": 4.0, "diff_file": "culprit.diff"})
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
    for f in ("old.png", "new.png"):
        (d / f).write_bytes(b"\x89PNG-" + f.encode())
    if render:
        (d / "renders" / f"{commits[1]['sha'][:10]}.png").write_bytes(b"\x89PNG-render")
    (d / "culprit.diff").write_text("diff --git a/x b/x\n", encoding="utf-8")
    return d


@pytest.fixture
def runs(tmp_path):
    root = tmp_path / "runs"
    make_run(root, "r1")
    return root


@pytest.fixture
def client(runs, tmp_path):
    ev = tmp_path / "results.json"
    ev.write_text(json.dumps({"label": "dev", "results": []}))
    app = create_app(runs, ev, web_dist=tmp_path / "no-dist", token=TOKEN)
    return TestClient(app, headers=AUTH)


# ---- access control -------------------------------------------------------------------------

def test_api_requires_token(runs, tmp_path):
    c = TestClient(create_app(runs, tmp_path / "e.json", web_dist=tmp_path / "nd", token=TOKEN))
    for path in ("/api/runs", "/api/runs/r1", "/api/runs/r1/files/old.png", "/api/eval", "/api/runs/r1/stream"):
        assert c.get(path).status_code == 401, path
    assert c.get("/api/runs", headers={"X-VBisect-Token": "wrong"}).status_code == 401
    assert c.get("/api/runs", headers=AUTH).status_code == 200
    assert c.get(f"/api/runs/r1/files/old.png?token={TOKEN}").status_code == 200  # <img> and EventSource use the query


@pytest.mark.parametrize("host", ["evil.com", "127.0.0.1.evil.com", "localhost.evil.com:8000", "10.0.0.5:8000"])
def test_rejects_foreign_host(client, host):
    assert client.get("/api/runs", headers={"Host": host}).status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8123", "localhost", "[::1]:8000"])
def test_accepts_loopback_host(client, host):
    assert client.get("/api/runs", headers={"Host": host}).status_code == 200


def test_rejects_foreign_origin(client):
    assert client.get("/api/runs", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/runs", headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_each_app_gets_its_own_random_token(runs, tmp_path):
    a, b = (create_app(runs, tmp_path / "e.json", web_dist=tmp_path / "nd") for _ in range(2))
    assert a.state.token != b.state.token and len(a.state.token) >= 24


# ---- routes ---------------------------------------------------------------------------------

def test_list_and_get_run(client):
    rows = client.get("/api/runs").json()
    assert [r["id"] for r in rows] == ["r1"]
    assert rows[0]["status"] == "done" and rows[0]["commits"] == 4 and rows[0]["date"].startswith("1970")
    events = client.get("/api/runs/r1").json()
    assert [e["type"] for e in events][0] == "run_started" and events[-1]["type"] == "run_done"


@pytest.mark.parametrize("rid", ["nope", "..", ".hidden", "a b", "%2e%2e", "r1%00"])
def test_invalid_run_ids_404(client, rid):
    assert client.get(f"/api/runs/{rid}").status_code in (404, 422)


@pytest.mark.parametrize("path", ["../r1/events.jsonl", "../../secret.txt", "..%2f..%2fsecret.txt", "%2e%2e/%2e%2e/secret.txt",
                                  "renders/../../secret.txt", "/etc/passwd", "C:/Windows/win.ini", "nope.png"])
def test_file_path_traversal_blocked(client, runs, path):
    (runs.parent / "secret.txt").write_text("top secret")
    r = client.get(f"/api/runs/r1/files/{path}")
    assert r.status_code == 404 and b"top secret" not in r.content


def test_file_served(client):
    r = client.get("/api/runs/r1/files/old.png")
    assert r.status_code == 200 and r.content.endswith(b"old.png")


def test_symlink_escape_blocked(client, runs, tmp_path):
    secret = tmp_path / "outside.txt"
    secret.write_text("outside")
    try:
        os.symlink(secret, runs / "r1" / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    assert client.get("/api/runs/r1/files/link.txt").status_code == 404


def test_half_written_last_line_and_garbage_are_tolerated(runs):
    p = runs / "r1" / "events.jsonl"
    p.write_text(p.read_text() + '{"ts": 105, "type": "step_st')
    assert len(read_events(runs / "r1")) == 5
    (runs / "bad").mkdir()
    (runs / "bad" / "events.jsonl").write_text("not json\n[1,2]\n")
    assert summarize(runs / "bad") is None


def test_malformed_run_not_listed(runs, tmp_path):
    (runs / "bad").mkdir()
    (runs / "bad" / "events.jsonl").write_text("not json\n")
    c = TestClient(create_app(runs, tmp_path / "e", web_dist=tmp_path / "nd", token=TOKEN), headers=AUTH)
    assert [r["id"] for r in c.get("/api/runs").json()] == ["r1"]


def test_eval_404_then_dev_fallback(runs, tmp_path):
    c = TestClient(create_app(runs, tmp_path / "results.json", web_dist=tmp_path / "nd", token=TOKEN), headers=AUTH)
    assert c.get("/api/eval").status_code == 404
    (tmp_path / "results.dev.json").write_text(json.dumps({"label": "dev", "results": [{"seed": 1}]}))
    assert c.get("/api/eval").json()["label"] == "dev"


# ---- SSE ------------------------------------------------------------------------------------

def sse_events(resp) -> list[dict]:
    return [json.loads(l[6:]) for l in resp.iter_lines() if l.startswith("data: ")]


def test_stream_finished_run_replays_everything_and_closes(client):
    with client.stream("GET", "/api/runs/r1/stream") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        got = sse_events(r)
    assert [e["type"] for e in got] == ["run_started", "step_started", "render_done", "step_done", "run_done"]


def test_stream_delivers_events_appended_while_open(tmp_path):
    root = tmp_path / "runs"
    d = make_run(root, "live", finished=False)
    c = TestClient(create_app(root, tmp_path / "e", web_dist=tmp_path / "nd", token=TOKEN), headers=AUTH)

    def finish():
        time.sleep(0.8)
        with open(d / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": 110.0, "type": "run_done", "culprit_sha": "x", "steps": 1, "skips": 0,
                                "api_calls": 0, "seconds": 1, "diff_file": None}) + "\n")

    t = threading.Thread(target=finish)
    t.start()
    with c.stream("GET", "/api/runs/live/stream") as r:
        got = sse_events(r)
    t.join()
    assert got[-1]["type"] == "run_done" and len(got) == 5


# ---- frontend hosting -----------------------------------------------------------------------

def test_index_gets_token_injected_and_assets_served(runs, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><head><title>x</title></head><body></body></html>")
    (dist / "assets" / "a.js").write_text("console.log(1)")
    c = TestClient(create_app(runs, web_dist=dist, token=TOKEN))
    page = c.get("/").text
    assert f'<meta name="vb-token" content="{TOKEN}">' in page
    assert c.get("/replay/anything").text == page  # SPA fallback
    assert c.get("/assets/a.js").status_code == 200
    assert c.get("/index.html").text == page
    assert c.get("/", headers={"Host": "evil.com"}).status_code == 403  # page (and token) never goes to a foreign host
    assert c.get("/../../etc/passwd").status_code in (200, 404)  # falls back to the SPA, never reads outside dist
    assert "root:" not in c.get("/..%2f..%2fetc/passwd").text


# ---- export ---------------------------------------------------------------------------------

@pytest.fixture
def fake_dist(tmp_path, monkeypatch):
    dist = tmp_path / "fake_dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><head></head></html>")
    (dist / "assets" / "app.js").write_text("//")
    monkeypatch.setattr(frontend_build, "ensure_built", lambda: dist)
    return dist


def test_discover_run_folder_parent_and_dedupe(tmp_path):
    root = tmp_path / "runs"
    a, b = make_run(root, "a"), make_run(root, "b")
    (root / "empty").mkdir()
    assert export_mod.discover([root]) == [a.resolve(), b.resolve()]
    assert export_mod.discover([a, root]) == [a.resolve(), b.resolve()]  # a not listed twice
    with pytest.raises(SystemExit):
        export_mod.discover([root / "empty"])
    with pytest.raises(SystemExit):
        export_mod.discover([tmp_path / "missing"])


def test_export_creates_missing_parents_and_copies_only_needed_files(runs, tmp_path, fake_dist):
    (runs / "r1" / "secrets.env").write_text("KEY=abc")
    (runs / "r1" / "run.json").write_text("{}")
    ev = tmp_path / "results.json"
    ev.write_text(json.dumps({"label": "test", "results": [{"seed": 1}]}))
    out = tmp_path / "deep" / "nested" / "site"
    export_mod.export([runs], ev, out)
    d = out / "data"
    assert json.loads((d / "index.json").read_text())[0]["id"] == "r1"
    assert (d / "runs" / "r1" / "events.jsonl").is_file() and (d / "runs" / "r1" / "old.png").is_file()
    assert (d / "runs" / "r1" / "culprit.diff").is_file()
    assert any((d / "runs" / "r1" / "renders").iterdir())
    assert not (d / "runs" / "r1" / "secrets.env").exists() and not (d / "runs" / "r1" / "run.json").exists()
    assert json.loads((d / "eval.json").read_text())["label"] == "test"
    assert (out / "index.html").is_file() and (out / ".nojekyll").is_file()
    assert [p.name for p in out.parent.iterdir()] == ["site"]  # no staging leftovers


def test_export_multiple_runs_from_parent(tmp_path, fake_dist):
    root = tmp_path / "runs"
    make_run(root, "a"), make_run(root, "b")
    export_mod.export([root], None, tmp_path / "site")
    index = json.loads((tmp_path / "site" / "data" / "index.json").read_text())
    assert sorted(r["id"] for r in index) == ["a", "b"]
    assert not (tmp_path / "site" / "data" / "eval.json").exists()


def test_export_never_follows_symlinks(runs, tmp_path, fake_dist):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"SECRET")
    sha = next(e["sha"] for e in read_events(runs / "r1") if e["type"] == "step_started")
    target = runs / "r1" / "renders" / f"{sha[:10]}.png"
    target.unlink()
    try:
        os.symlink(secret, target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    export_mod.export([runs], None, tmp_path / "site")
    copied = list((tmp_path / "site").rglob("*.png"))
    assert all(p.read_bytes() != b"SECRET" for p in copied)
    assert not (tmp_path / "site" / "data" / "runs" / "r1" / "renders" / target.name).exists()


def test_export_missing_image_is_a_warning_not_a_crash(runs, tmp_path, fake_dist, capsys):
    for p in (runs / "r1" / "renders").iterdir():
        p.unlink()
    export_mod.export([runs], None, tmp_path / "site")
    assert "missing" in capsys.readouterr().err
    assert (tmp_path / "site" / "data" / "index.json").is_file()


def test_export_skips_malformed_runs_but_fails_if_none_valid(runs, tmp_path, fake_dist, capsys):
    bad = runs / "bad"
    bad.mkdir()
    (bad / "events.jsonl").write_text("garbage\n")
    export_mod.export([runs], None, tmp_path / "site")
    assert "skipping" in capsys.readouterr().err
    assert [r["id"] for r in json.loads((tmp_path / "site" / "data" / "index.json").read_text())] == ["r1"]
    only_bad = tmp_path / "only"
    (only_bad / "bad").mkdir(parents=True)
    (only_bad / "bad" / "events.jsonl").write_text("garbage\n")
    with pytest.raises(SystemExit):
        export_mod.export([only_bad], None, tmp_path / "site2")
    assert not (tmp_path / "site2").exists()


def test_export_refuses_to_replace_unrelated_folder(runs, tmp_path, fake_dist):
    out = tmp_path / "precious"
    out.mkdir()
    (out / "thesis.docx").write_text("do not delete")
    with pytest.raises(SystemExit):
        export_mod.export([runs], None, out)
    assert (out / "thesis.docx").read_text() == "do not delete"
    f = tmp_path / "afile"
    f.write_text("x")
    with pytest.raises(SystemExit):
        export_mod.export([runs], None, f)


def test_export_replaces_a_previous_export(runs, tmp_path, fake_dist):
    out = tmp_path / "site"
    export_mod.export([runs], None, out)
    (out / "data" / "stale.txt").write_text("old")
    export_mod.export([runs], None, out)
    assert not (out / "data" / "stale.txt").exists() and (out / "data" / "index.json").is_file()
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


def test_failed_export_keeps_the_previous_site(runs, tmp_path, fake_dist):
    out = tmp_path / "site"
    export_mod.export([runs], None, out)
    broken = tmp_path / "broken"
    (broken / "x").mkdir(parents=True)
    (broken / "x" / "events.jsonl").write_text("nope\n")
    with pytest.raises(SystemExit):
        export_mod.export([broken], None, out)
    assert (out / "data" / "index.json").is_file()
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


@pytest.mark.parametrize("where", ["same", "parent", "child"])
def test_export_rejects_output_overlapping_runs(runs, tmp_path, fake_dist, where):
    out = {"same": runs / "r1", "parent": runs, "child": runs / "r1" / "site"}[where]
    with pytest.raises(SystemExit):
        export_mod.export([runs / "r1"], None, out)
    assert (runs / "r1" / "events.jsonl").is_file()


def test_export_rejects_bad_eval(runs, tmp_path, fake_dist):
    bad = tmp_path / "results.json"
    bad.write_text("{not json")
    with pytest.raises(SystemExit):
        export_mod.export([runs], bad, tmp_path / "site")
    bad.write_text(json.dumps({"nope": 1}))
    with pytest.raises(SystemExit):
        export_mod.export([runs], bad, tmp_path / "site")
    assert not (tmp_path / "site").exists()


def test_exported_events_paths_cannot_escape_the_run(runs, tmp_path, fake_dist, capsys):
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"SECRET")
    p = runs / "r1" / "events.jsonl"
    lines = [json.loads(l) for l in p.read_text().splitlines()]
    lines[0]["old_ref_img"] = "../../secret.png"
    lines[0]["new_ref_img"] = str(secret)
    p.write_text("".join(json.dumps(e) + "\n" for e in lines))
    export_mod.export([runs], None, tmp_path / "site")
    assert all(f.read_bytes() != b"SECRET" for f in (tmp_path / "site").rglob("*.png"))


# ---- CLI ------------------------------------------------------------------------------------

def test_cli_dispatches_export_and_keeps_bisect_flags(runs, tmp_path, fake_dist, capsys):
    from vbisect import cli
    assert cli.main(["export", "--runs", str(runs), "--eval", str(tmp_path / "none.json"), "--out", str(tmp_path / "site")]) == 0
    assert (tmp_path / "site" / "data" / "index.json").is_file()
    parser = cli.build_parser()
    a = parser.parse_args(["--repo", "r", "--good", "g", "--focus", "f", "--good-render", "--ui"])
    assert a.ui and a.judge == "gemma" and a.bad == "HEAD"
    with pytest.raises(SystemExit):
        cli.main(["serve", "--help"])


def test_export_skips_files_reported_as_symlinks(runs, tmp_path, fake_dist, monkeypatch):
    """Same rule as the symlink test above, without needing symlink privileges (Windows)."""
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name.endswith(".png") and self.parent.name == "renders" or real(self))
    export_mod.export([runs], None, tmp_path / "site")
    assert not list((tmp_path / "site" / "data" / "runs" / "r1").rglob("renders/*"))
    assert (tmp_path / "site" / "data" / "runs" / "r1" / "old.png").is_file()
