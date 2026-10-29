"""Install (cached by lockfile hash), build, serve, stop."""
from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEPS_CACHE = Path.home() / ".cache" / "vbisect" / "deps"
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")


class BuildFailed(RuntimeError):
    pass


_server: subprocess.Popen | None = None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _lock_hash(wt: Path) -> str | None:
    for name in LOCKFILES:
        p = wt / name
        if p.exists():
            return hashlib.sha256(p.read_bytes()).hexdigest()[:20]
    return None


def _sh(cmd: str, cwd: Path, timeout: int) -> None:
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise BuildFailed(f"timeout: {cmd}") from e
    if r.returncode != 0:
        raise BuildFailed(f"{cmd} failed:\n{(r.stdout + r.stderr)[-2000:]}")


def install(wt: Path, install_cmd: str, timeout: int) -> str:
    """Returns 'install' or 'install-cached'."""
    key = _lock_hash(wt)
    target = wt / "node_modules"
    if key:
        cached = DEPS_CACHE / key / "node_modules"
        if cached.exists():
            if target.exists() or target.is_symlink():
                shutil.rmtree(target, ignore_errors=True)
            try:
                os.symlink(cached, target, target_is_directory=True)
            except OSError:
                shutil.copytree(cached, target, symlinks=True)
            return "install-cached"
    _sh(install_cmd, wt, timeout * 3)
    if key and target.exists():
        dest = DEPS_CACHE / key / "node_modules"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, dest, symlinks=True, dirs_exist_ok=True)
    return "install"


def build_and_serve(wt: Path, install_cmd: str, build_cmd: str, serve_cmd: str,
                    timeout: int = 120, progress=None) -> str:
    global _server

    def tick(phase, t0):
        if progress:
            progress(phase, round(time.time() - t0, 2))

    t0 = time.time()
    phase = install(wt, install_cmd, timeout)
    tick(phase, t0)
    t0 = time.time()
    _sh(build_cmd, wt, timeout)
    tick("build", t0)

    t0 = time.time()
    port = _free_port()
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" \
        else {"start_new_session": True}
    _server = subprocess.Popen(serve_cmd.format(port=port), cwd=wt, shell=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        if _server.poll() is not None:
            raise BuildFailed("serve command exited early")
        try:
            urllib.request.urlopen(base, timeout=1)
            tick("serve", t0)
            return base
        except Exception:
            time.sleep(0.3)
    raise BuildFailed("server did not respond within 30s")


def stop_server() -> None:
    global _server
    if _server is None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(_server.pid)], capture_output=True)
        else:
            import signal
            os.killpg(os.getpgid(_server.pid), signal.SIGTERM)
    except Exception:
        pass
    _server = None
