#!/usr/bin/env python3
"""Personal project notes for agent hooks.

Adds my notes for the current repository to the agent's context. The script
finds a notes file by remote URL, not by checkout path, so one file applies to
each checkout on each machine. `github.com/gfx-rs/wgpu.md` under NOTES_DIR
applies to a repository that has a remote for that project, under any remote
name. Keys are lowercase.

Wired to SessionStart and SubagentStart. The hook payload arrives as JSON on
stdin, and its `cwd` selects the repository. With no matching file the script
prints nothing.

Stdlib only, and targets Python 3.8, for the same reasons as caffeine.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

NOTES_DIR = Path.home() / ".config" / "project-notes"

# jj first: a jj workspace has no .git directory of its own.
REMOTE_COMMANDS = (
    ("jj", "--no-pager", "--ignore-working-copy", "git", "remote", "list"),
    ("git", "remote", "-v"),
)

# Accepts `git@host:owner/repo.git`, `https://host/owner/repo` and
# `ssh://git@host:22/owner/repo.git`.
REMOTE_URL = re.compile(
    r"^(?:[a-z+]+://)?(?:[^@/]+@)?(?P<host>[^:/]+)(?::\d+)?[:/](?P<path>.+?)(?:\.git)?/?$"
)


def remote_urls(cwd: str) -> list[str]:
    """Returns the remote URLs of the repository that contains `cwd`."""
    for command in REMOTE_COMMANDS:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                # Stops a console window flash on Windows.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            # Each line is `<name> <url>`; git adds ` (fetch)` or ` (push)`.
            return [line.split()[1] for line in result.stdout.splitlines() if len(line.split()) >= 2]
    return []


def project_key(url: str) -> str | None:
    """Converts a remote URL to a `host/owner/repo` key."""
    match = REMOTE_URL.match(url)
    if match is None:
        return None
    key = "{}/{}".format(match["host"], match["path"]).lower()
    if ".." in key.split("/"):
        return None
    return key


def main() -> None:
    payload = json.load(sys.stdin)

    keys = []
    for url in remote_urls(payload["cwd"]):
        key = project_key(url)
        if key is not None and key not in keys:
            keys.append(key)

    sections = []
    for key in keys:
        path = NOTES_DIR / (key + ".md")
        if path.is_file():
            notes = path.read_text(encoding="utf-8").strip()
            sections.append("The user's personal notes for {}:\n\n{}".format(key, notes))
    if not sections:
        return

    output = {
        "hookSpecificOutput": {
            "hookEventName": payload["hook_event_name"],
            "additionalContext": "\n\n".join(sections),
        }
    }
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
