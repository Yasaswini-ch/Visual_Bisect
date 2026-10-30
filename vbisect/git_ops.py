"""Thin wrappers over the git CLI. The user's checkout is never touched."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path


def git(repo: str | Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=check, encoding="utf-8", errors="replace")


def resolve(repo: str, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()


def commit_list(repo: str, good: str, bad: str) -> list[dict]:
    fmt = "%H%x1f%s%x1f%aI%x1f%an"
    out = git(repo, "rev-list", "--reverse", "--ancestry-path", f"--format={fmt}",
              "--no-commit-header", f"{good}..{bad}").stdout
    commits = []
    for line in out.splitlines():
        sha, subject, date, author = line.split("\x1f")
        commits.append({"sha": sha, "subject": subject, "date": date, "author": author})
    return commits


def commit_info(repo: str, sha: str, max_diff: int = 20000) -> dict:
    fmt = "%H%x1f%an%x1f%aI%x1f%s"
    h, author, date, subject = git(repo, "show", "-s", f"--format={fmt}", sha).stdout.strip().split("\x1f")
    stat = git(repo, "show", "--stat", "--format=", sha).stdout
    diff = git(repo, "show", "--format=", sha).stdout
    return {"sha": h, "author": author, "date": date, "subject": subject,
            "stat": stat, "diff": diff, "diff_truncated": diff[:max_diff]}


def make_worktree(repo: str, ref: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix="vbisect-wt-"))
    git(repo, "worktree", "add", "--detach", str(path), ref)
    return path


def cleanup(repo: str, worktree: Path) -> None:
    from .builder import _is_link, remove_link

    nm = worktree / "node_modules"
    if _is_link(nm):  # a link into the shared dependency cache: drop the link, never the cache
        remove_link(nm)
    git(repo, "worktree", "remove", "--force", str(worktree), check=False)


def run_bisect(repo: str, worktree: Path, good: str, bad: str, run_json: Path) -> dict:
    """Run real `git bisect run`. Returns {"culprit": sha|None, "log": str}."""
    git(worktree, "bisect", "start", "--term-old=old", "--term-new=new", bad, good)
    try:
        p = git(worktree, "bisect", "run", sys.executable, "-m", "vbisect.oracle",
                "--config", str(run_json), check=False)
        log = p.stdout + p.stderr
    finally:
        git(worktree, "bisect", "reset", check=False)
    m = re.search(r"^([0-9a-f]{40}) is the first new commit", log, re.M)
    return {"culprit": m.group(1) if m else None, "log": log, "returncode": p.returncode}
