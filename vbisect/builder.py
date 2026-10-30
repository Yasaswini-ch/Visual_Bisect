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


def _group_kwargs() -> dict:
    return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" \
        else {"start_new_session": True}


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill a shell and everything it started (subprocess.run's timeout only kills the shell on Windows,
    then waits forever on the grandchildren's pipes)."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:  # Windows directory junction
        return bool(os.lstat(path).st_file_attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False


def remove_link(path: Path) -> None:
    """Remove a symlink/junction without touching what it points to (never rmtree a link)."""
    try:
        os.rmdir(path)
    except (NotADirectoryError, OSError):
        try:
            os.unlink(path)
        except OSError:
            pass


def _link_dir(target: Path, source: Path) -> None:
    """Make `target` point at `source`: symlink, else a Windows junction (no privilege needed), else copy.
    Copying many node_modules at once stalled concurrent runs."""
    try:
        os.symlink(source, target, target_is_directory=True)
        return
    except OSError:
        pass
    if sys.platform == "win32":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(source)], capture_output=True)
        if r.returncode == 0:
            return
    shutil.copytree(source, target, symlinks=True)


def _sh(cmd: str, cwd: Path, timeout: int) -> None:
    if not cmd.strip():  # e.g. the "static" preset has nothing to install or build
        return
    proc = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", **_group_kwargs())
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        _kill_tree(proc)
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        raise BuildFailed(f"timeout: {cmd}") from e
    if proc.returncode != 0:
        raise BuildFailed(f"{cmd} failed:\n{(out or '')[-2000:]}")


def install(wt: Path, install_cmd: str, timeout: int) -> str:
    """Returns 'install' or 'install-cached'."""
    key = _lock_hash(wt)
    target = wt / "node_modules"
    if key:
        cached = DEPS_CACHE / key / "node_modules"
        if cached.exists():
            if _is_link(target):
                remove_link(target)
            elif target.exists():
                shutil.rmtree(target, ignore_errors=True)
            _link_dir(target, cached)
            return "install-cached"
    _sh(install_cmd, wt, timeout * 3)
    if key and target.exists() and not _is_link(target):
        dest = DEPS_CACHE / key / "node_modules"
        if not dest.exists():  # first writer wins; concurrent runs must not rewrite a cache others use
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.parent / f"tmp-{os.getpid()}"
            shutil.copytree(target, tmp, symlinks=True)
            try:
                os.rename(tmp, dest)
            except OSError:
                shutil.rmtree(tmp, ignore_errors=True)
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
    _server = subprocess.Popen(serve_cmd.format(port=port), cwd=wt, shell=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_group_kwargs())
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
    _kill_tree(_server)
    _server = None
