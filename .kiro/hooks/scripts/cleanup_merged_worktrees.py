#!/usr/bin/env python3
"""Stop hook: remove worktrees under .worktrees/ whose branch is merged into its parent.

"Parent" is the branch the worktree branch was created from, read from the branch
reflog entry "branch: Created from <parent>" (falls back to main). A worktree is
removed only when ALL of these hold:

1. It lives under <repo>/.worktrees/, is on a branch, and is not locked.
2. Its branch has moved past the commit it was created at. A fresh branch with no
   commits points at its parent's tip and would otherwise look "merged".
3. The branch tip is an ancestor of the parent, locally or on origin (covers both a
   local `git merge --ff-only` and a GitHub merge-commit PR).
4. `git status --porcelain` is empty (no uncommitted or untracked work). Ignored files
   such as .venv/ do not count and are removed with the worktree.

Removal uses `git worktree remove` without --force, then `git branch -d` (which git
refuses for unmerged branches). Anything uncertain is skipped. Actions are appended
to <git-common-dir>/worktree-cleanup.log. Pass --dry-run to only report.
Standard library only.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

FALLBACK_PARENT = "main"


def git(repo: Path, *args: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def worktrees(repo: Path) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into dicts (path, branch, locked, ...)."""
    out = git(repo, "worktree", "list", "--porcelain").stdout
    entries: list[dict[str, str]] = []
    for block in out.strip().split("\n\n"):
        entry: dict[str, str] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            entry[key] = value
        if "worktree" in entry:
            entries.append(entry)
    return entries


def creation_point(repo: Path, branch: str) -> tuple[str, str] | None:
    """Return (start_sha, parent_branch) from the branch's oldest reflog entry."""
    out = git(repo, "reflog", "show", "--format=%H%x00%gs", f"refs/heads/{branch}").stdout
    lines = [ln for ln in out.splitlines() if "\x00" in ln]
    if not lines:
        return None
    sha, subject = lines[-1].split("\x00", 1)
    if not subject.startswith("branch: Created from "):
        return None  # Reflog expired or unusual history: don't guess.
    parent = subject.removeprefix("branch: Created from ").strip()
    if parent.startswith("refs/heads/"):
        parent = parent.removeprefix("refs/heads/")
    if parent.startswith("origin/"):
        parent = parent.removeprefix("origin/")
    if parent == "HEAD" or git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{parent}").returncode:
        parent = FALLBACK_PARENT
    return sha, parent


def is_ancestor(repo: Path, commit: str, ref: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", commit, ref).returncode == 0


def log(repo: Path, message: str) -> None:
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    print(message)
    if common:
        with open(Path(common) / "worktree-cleanup.log", "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {message}\n")


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    repo_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--repo=")), None)
    repo = Path(repo_arg) if repo_arg else Path(__file__).resolve().parents[3]
    top = git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    if not top:
        return 0
    repo = Path(top)
    managed_root = (repo / ".worktrees").resolve()
    cwd = Path(os.getcwd()).resolve()

    candidates = []
    for wt in worktrees(repo):
        path = Path(wt["worktree"]).resolve()
        branch = wt.get("branch", "").removeprefix("refs/heads/")
        if managed_root not in path.parents or not branch or "locked" in wt:
            continue
        if path == cwd or path in cwd.parents:
            continue  # Never delete the directory this process runs in.
        candidates.append((path, branch, wt["HEAD"]))
    if not candidates:
        return 0

    git(repo, "fetch", "--quiet", "origin", timeout=20)  # Best effort; offline is fine.

    for path, branch, tip in candidates:
        origin = creation_point(repo, branch)
        if origin is None:
            continue
        start_sha, parent = origin
        if tip == start_sha:
            continue  # No work committed yet.
        refs = [r for r in (parent, f"origin/{parent}")
                if git(repo, "rev-parse", "--verify", "--quiet", r).returncode == 0]
        merged_into = next((r for r in refs if is_ancestor(repo, tip, r)), None)
        if merged_into is None:
            continue
        if git(path, "status", "--porcelain").stdout.strip():
            log(repo, f"SKIP {path}: {branch} is merged into {merged_into} but has uncommitted or untracked changes")
            continue
        if dry_run:
            log(repo, f"DRY-RUN would remove {path} ({branch} merged into {merged_into})")
            continue
        removed = git(repo, "worktree", "remove", str(path))
        if removed.returncode != 0:
            log(repo, f"SKIP {path}: git worktree remove failed: {removed.stderr.strip()}")
            continue
        deleted = git(repo, "branch", "-d", branch)
        note = "branch deleted" if deleted.returncode == 0 else f"branch kept: {deleted.stderr.strip()}"
        log(repo, f"REMOVED {path} ({branch} merged into {merged_into}); {note}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # A cleanup hook must never break the agent loop.
        print(f"worktree cleanup skipped: {exc}", file=sys.stderr)
        sys.exit(0)
