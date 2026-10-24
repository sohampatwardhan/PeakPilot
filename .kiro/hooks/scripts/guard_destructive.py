#!/usr/bin/env python3
"""PreToolUse guard: ask the user before the agent runs a destructive shell command.

Kiro pipes the tool-call context to this script as JSON on stdin. If the shell command
matches a destructive pattern (rm, git reset --hard, force push, ...), the script prints a
PreToolUse decision asking the user to confirm. Otherwise it prints nothing, and the call
proceeds under the IDE's normal approval settings.

The script never blocks outright (no exit code 2): destructive commands are sometimes the
right call, so the decision goes to the user. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys

# Each entry: (regex, human-readable reason). Matched against every command segment
# split on ;, &&, ||, | and newlines, so `cd x && rm -rf y` is still caught.
DESTRUCTIVE = [
    (r"^(sudo\s+)?rm(\s|$)", "deletes files (rm)"),
    (r"^(sudo\s+)?rmdir(\s|$)", "removes directories (rmdir)"),
    (r"^(sudo\s+)?unlink(\s|$)", "deletes a file (unlink)"),
    (r"^(sudo\s+)?shred(\s|$)", "destroys file contents (shred)"),
    (r"^(sudo\s+)?truncate(\s|$)", "truncates files (truncate)"),
    (r"^(sudo\s+)?dd(\s|$)", "raw disk/file writes (dd)"),
    (r"^(sudo\s+)?mkfs", "formats a filesystem (mkfs)"),
    (r"^(sudo\s+)?mv(\s|$)", "moves files and can overwrite the destination (mv)"),
    (r"^(sudo\s+)?(chmod|chown)\s+(-\w*R|--recursive)", "recursive permission/owner change"),
    (r"^(sudo\s+)?(kill|pkill|killall)(\s|$)", "terminates processes"),
    (r"^sudo(\s|$)", "runs with elevated privileges (sudo)"),
    (r"\bfind\b.*\s-delete\b", "find -delete removes files"),
    (r"\bxargs\b.*\brm\b", "xargs rm removes files"),
    (r"^git\s+reset\s+.*--hard", "discards local changes (git reset --hard)"),
    (r"^git\s+clean(\s|$)", "deletes untracked files (git clean)"),
    (r"^git\s+push\s+.*(--force|--force-with-lease|\s-f(\s|$))", "rewrites remote history (force push)"),
    (r"^git\s+push\s+.*--delete", "deletes a remote branch"),
    (r"^git\s+push\s+\S+\s+:\S+", "deletes a remote branch (push :ref)"),
    (r"^git\s+branch\s+.*-D(\s|$)", "force-deletes a branch (git branch -D)"),
    (r"^git\s+(checkout|restore)\s+.*(--\s|\s\.$)", "discards working-tree changes"),
    (r"^git\s+stash\s+(drop|clear)", "drops stashed work"),
    (r"^git\s+rebase(\s|$)", "rewrites commit history (rebase)"),
    (r"^git\s+commit\s+.*--amend", "rewrites the last commit (--amend)"),
    (r"^gh\s+(repo|release)\s+delete", "deletes a GitHub repo/release"),
    (r"^gh\s+pr\s+merge", "merges a pull request"),
    (r"^(pip3?|python3?\s+-m\s+pip)\s+uninstall", "uninstalls packages"),
    (r"^(brew|npm|cargo)\s+uninstall", "uninstalls packages"),
    (r"^npm\s+(rm|remove)(\s|$)", "uninstalls packages"),
]

# Output redirection that overwrites a real file (`> file`), ignoring `>>`, `2>&1`,
# and redirects to /dev/null.
OVERWRITE_REDIRECT = re.compile(r"(?<![>&0-9])>(?!>|&)\s*(?!/dev/null)\S")


def extract_command(payload: object) -> str:
    """Find the shell command in the hook payload without assuming one exact schema."""
    if isinstance(payload, dict):
        for key in ("command", "cmd"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        for value in payload.values():
            found = extract_command(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = extract_command(value)
            if found:
                return found
    return ""


def strip_noise(command: str) -> str:
    """Remove heredoc bodies and quoted strings so their contents aren't scanned.

    Without this, a `>` comparison inside an inline Python heredoc or the word "rm" in a
    commit message would count as destructive. This is a heuristic, not a shell parser:
    destructive code hidden inside a quoted `python -c` string is not detected.
    """
    kept: list[str] = []
    terminator: str | None = None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        heredoc = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if heredoc:
            terminator = heredoc.group(1)
        kept.append(line)
    text = "\n".join(kept)
    text = re.sub(r"'[^']*'", "''", text)
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', text)


def segments(command: str) -> list[str]:
    parts = re.split(r"&&|\|\||;|\||\n", command)
    return [p.strip() for p in parts if p.strip()]


def reasons_for(command: str) -> list[str]:
    command = strip_noise(command)
    found: list[str] = []
    for seg in segments(command):
        for pattern, reason in DESTRUCTIVE:
            if re.search(pattern, seg) and reason not in found:
                found.append(reason)
    if OVERWRITE_REDIRECT.search(command):
        found.append("overwrites a file via > redirection")
    return found


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Unparseable input: stay out of the way.

    command = extract_command(payload)
    if not command:
        return 0

    reasons = reasons_for(command)
    if reasons:
        decision = {
            "hookSpecificOutput": {
                "permissionDecision": "ask",
                "permissionDecisionReason": "Destructive command: " + "; ".join(reasons),
            }
        }
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
