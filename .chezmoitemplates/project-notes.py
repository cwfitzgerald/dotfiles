#!/usr/bin/env python3
"""Personal project notes for agent hooks.

Adds my notes for the current repository to the agent's context. The script
finds a notes file by remote URL, not by checkout path, so one file applies to
each checkout on each machine. `github.com/gfx-rs/wgpu.md` under NOTES_DIR
applies to a repository that has a remote for that project, under any remote
name. Keys are lowercase.

Wired to SessionStart, SubagentStart and PostToolUse. The hook payload arrives
as JSON on stdin. The directory of the file that a tool used selects the
repository, or `cwd` when the payload has no file. Thus a session that starts
above its repositories gets the notes when it first uses a file in one.
PostToolUse gives each agent the notes for a project one time, until the next
SessionStart. With no notes to give the script prints nothing.

Stdlib only, and targets Python 3.8, for the same reasons as caffeine.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

NOTES_DIR = Path.home() / ".config" / "project-notes"

# One file per session. Each line is `<agent id> <project key>` for notes
# that the agent has received.
STATE_DIR = Path(tempfile.gettempdir()) / "project-notes"

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

    event = payload["hook_event_name"]
    file_path = payload.get("tool_input", {}).get("file_path")
    directory = str(Path(payload["cwd"], file_path).parent) if file_path else payload["cwd"]

    keys = []
    for url in remote_urls(directory):
        key = project_key(url)
        if key is not None and key not in keys:
            keys.append(key)

    # Cursor sends `conversation_id` in place of `session_id` on tool events.
    session = payload.get("session_id") or payload.get("conversation_id")
    state = STATE_DIR / "{}.txt".format(session)
    if event == "SessionStart":
        state.unlink(missing_ok=True)
    # The start events are new contexts, so only PostToolUse reads the record.
    seen = []
    if event == "PostToolUse" and state.is_file():
        seen = state.read_text(encoding="utf-8").splitlines()
    agent = payload.get("agent_id", "main")

    sections = []
    entries = []
    for key in keys:
        entry = "{} {}".format(agent, key)
        path = NOTES_DIR / (key + ".md")
        if entry not in seen and path.is_file():
            notes = path.read_text(encoding="utf-8").strip()
            sections.append("The user's personal notes for {}:\n\n{}".format(key, notes))
            entries.append(entry)
    if not sections:
        return

    STATE_DIR.mkdir(mode=0o700, exist_ok=True)
    with state.open("a", encoding="utf-8") as file:
        file.write("".join(entry + "\n" for entry in entries))

    output = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "\n\n".join(sections),
        }
    }
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
