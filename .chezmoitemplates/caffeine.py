#!/usr/bin/env python3
"""Self-healing, multi-session keep-awake for agent hooks.

Each agent session owns one state file under STATE_DIR describing whether it
wants the machine awake: a foreground turn in progress (turn=1) or background
agents running (bg>0). A single "keeper" process re-asserts the OS wake lock
while ANY session wants awake, and exits (releasing it) once none do.

State is namespaced per session, so one session's SessionStart `reset` never
touches another's, and every event stamps a rolling expiry so a crashed
session's stale hold is swept up automatically -- no leaked reference counts,
no cross-session sabotage.

bg is not a pure counter: SubagentStop also fires for agents that never passed
through a PreToolUse acquire (hidden housekeeping agents, resumed agents), so
blind decrements drain holds belonging to still-running work. Stop and
SubagentStop payloads carry an authoritative `background_tasks` list, so those
events *reconcile* bg from it instead of doing arithmetic; the acquire counter
only bridges the gap between an agent spawn and the next reconciling event.

Wake backends: SetThreadExecutionState on Windows, caffeinate(8) on macOS.
Elsewhere the keeper only tracks state and logs a warning.

Stdlib only, and hooks must invoke it via pythonw on Windows: a console-
subsystem interpreter spawned by a console-less hook harness allocates a
visible console window on every event.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(tempfile.gettempdir()) / "claude-caffeine"
KEEPER_PID_FILE = STATE_DIR / "keeper.pid"
LOG_FILE = STATE_DIR / "caffeine.log"
PAYLOAD_LOG_FILE = STATE_DIR / "hookdebug.log"
LOCK_DIR = STATE_DIR / ".lock"

INTERVAL = 60  # keeper re-check cadence, seconds
STALE_TTL = 7200  # a hold is ignored this many seconds after its last refresh
LOG_ROTATE_BYTES = 1_000_000

ACTIONS = ("on", "off", "acquire", "release", "reset", "status", "__keeper")


def now() -> int:
    return int(time.time())


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def append_rotated(path: Path, line: str) -> None:
    try:
        if path.exists() and path.stat().st_size > LOG_ROTATE_BYTES:
            path.replace(path.with_suffix(path.suffix + ".1"))
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def log(msg: str) -> None:
    """Append-only audit trail of every state transition, so a miscount can be
    reconstructed and corrected after the fact."""
    append_rotated(LOG_FILE, f"{timestamp()} pid={os.getpid()} {msg}")


def log_payload(action: str, raw: str) -> None:
    """Raw hook payloads, kept separately: they identify exactly which agent or
    hidden task produced each event when the audit trail looks wrong."""
    compact = " ".join(raw.split())
    if len(compact) > 2500:
        compact = compact[:2500] + "...[truncated]"
    append_rotated(PAYLOAD_LOG_FILE, f"{timestamp()} action={action} raw={compact}")


# ---------------------------------------------------------------- hook input


def read_payload() -> dict:
    """The hook harness supplies event JSON on stdin. Only read when stdin is
    redirected; a manual invocation from a terminal has none, and pythonw
    without one has no stdin at all."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    raw = sys.stdin.read()
    if raw.strip():
        log_payload(sys.argv[1] if len(sys.argv) > 1 else "?", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {}


def session_id(payload: dict) -> str:
    for key in ("session_id", "sessionId", "conversation_id", "thread_id"):
        if payload.get(key):
            return str(payload[key])
    return "default"


def session_file(sid: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "_.-" else "_" for c in sid)
    return STATE_DIR / f"sess-{safe}.json"


def running_background_tasks(payload: dict, exclude_id: str | None = None):
    """Count of live background tasks per the payload's authoritative list,
    or None when this event doesn't carry one (PreToolUse, UserPromptSubmit).
    A SubagentStop's own agent may still be listed as running; exclude it."""
    tasks = payload.get("background_tasks")
    if tasks is None:
        return None
    return sum(
        1 for t in tasks if t.get("status") == "running" and t.get("id") != exclude_id
    )


# --------------------------------------------------------------- state files


def read_session(path: Path) -> dict:
    try:
        # utf-8-sig: the retired PowerShell variant wrote session files with a
        # BOM; live sessions started under it still share this state dir.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return {
            "turn": int(data["turn"]),
            "bg": int(data["bg"]),
            "expiry": int(data["expiry"]),
        }
    except (OSError, ValueError, KeyError):
        return {"turn": 0, "bg": 0, "expiry": 0}


def write_session(path: Path, state: dict) -> None:
    state["expiry"] = now() + STALE_TTL
    path.write_text(json.dumps(state), encoding="utf-8")


def any_wants_awake() -> bool:
    t = now()
    for f in STATE_DIR.glob("sess-*.json"):
        s = read_session(f)
        if t < s["expiry"] and (s["turn"] == 1 or s["bg"] > 0):
            return True
    return False


# --------------------------------------------------------------------- lock


def acquire_lock(action: str, sid: str) -> None:
    """Hooks from parallel events race on the same session file's
    read-modify-write; serialize under a mkdir lock. After ~10s of waiting,
    steal it -- actions finish in milliseconds, so an old lock means its
    holder crashed."""
    tries = 0
    while True:
        try:
            LOCK_DIR.mkdir()
            return
        except FileExistsError:
            tries += 1
            if tries >= 200:
                log(f"lock-steal action={action} sid={sid}")
                try:
                    LOCK_DIR.rmdir()
                except OSError:
                    pass
                tries = 0
            time.sleep(0.05)


def release_lock() -> None:
    try:
        LOCK_DIR.rmdir()
    except OSError:
        pass


# ------------------------------------------------------------------- keeper


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        query_limited, still_active = 0x1000, 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(query_limited, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def keeper_pid() -> int:
    try:
        return int(KEEPER_PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0


def keeper_alive() -> bool:
    return pid_exists(keeper_pid())


def start_keeper() -> None:
    if keeper_alive():
        return
    kwargs: dict = dict(
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    cmd = [sys.executable, os.path.abspath(__file__), "__keeper"]
    if os.name == "nt":
        # DETACHED_PROCESS: no console, so no window even from console python.
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        # Escape the caller's job object, else the keeper dies with the hook's
        # process tree; fall back for jobs that forbid breakaway.
        breakaway = 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
        try:
            proc = subprocess.Popen(cmd, creationflags=flags | breakaway, **kwargs)
        except OSError:
            proc = subprocess.Popen(cmd, creationflags=flags, **kwargs)
    else:
        kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
    KEEPER_PID_FILE.write_text(str(proc.pid))
    log(f"keeper-start pid={proc.pid}")


def stop_keeper() -> None:
    pid = keeper_pid()
    if pid_exists(pid):
        log(f"keeper-kill pid={pid}")
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    KEEPER_PID_FILE.unlink(missing_ok=True)


def stop_keeper_if_idle() -> None:
    """Stop the keeper only if nothing wants awake anymore; otherwise leave it
    so other sessions keep their lock."""
    if not any_wants_awake():
        stop_keeper()


class WakeLock:
    """Platform wake assertion. hold() must be safe to call repeatedly."""

    def __init__(self) -> None:
        self.caffeinate: subprocess.Popen | None = None
        if os.name != "nt" and sys.platform != "darwin":
            log("keeper-warn no wake backend on this platform; tracking only")

    def hold(self) -> None:
        if os.name == "nt":
            import ctypes

            es_continuous, es_system, es_display = 0x80000000, 0x1, 0x2
            ctypes.windll.kernel32.SetThreadExecutionState(
                es_continuous | es_system | es_display
            )
        elif sys.platform == "darwin" and self.caffeinate is None:
            # -w ties the assertion to the keeper's lifetime, even if killed.
            self.caffeinate = subprocess.Popen(
                ["caffeinate", "-dis", "-w", str(os.getpid())]
            )

    def drop(self) -> None:
        if os.name == "nt":
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        elif self.caffeinate is not None:
            self.caffeinate.terminate()
            self.caffeinate = None


def run_keeper() -> None:
    wake = WakeLock()
    while True:
        t = now()
        wants = False
        for f in STATE_DIR.glob("sess-*.json"):
            s = read_session(f)
            if t >= s["expiry"]:
                log(f"keeper-sweep removed {f.name} turn={s['turn']} bg={s['bg']}")
                f.unlink(missing_ok=True)
                continue
            if s["turn"] == 1 or s["bg"] > 0:
                wants = True
        if not wants:
            wake.drop()
            log("keeper-exit (idle)")
            KEEPER_PID_FILE.unlink(missing_ok=True)
            return
        wake.hold()
        time.sleep(INTERVAL)


# ------------------------------------------------------------------ actions


def transition(sid: str, path: Path, action: str, payload: dict) -> dict:
    s = read_session(path)
    prev = f"turn={s['turn']} bg={s['bg']}"

    if action == "on":  # foreground turn started
        s["turn"] = 1
    elif action == "acquire":  # background agent spawned
        s["bg"] += 1
    elif action == "release":  # a subagent stopped -- reconcile if possible
        n = running_background_tasks(payload, exclude_id=payload.get("agent_id"))
        s["bg"] = n if n is not None else max(0, s["bg"] - 1)
    elif action == "off":  # foreground turn ended -- reconcile if possible
        s["turn"] = 0
        n = running_background_tasks(payload)
        if n is not None:
            s["bg"] = n
    write_session(path, s)
    log(f"{action} sid={sid} {prev} -> turn={s['turn']} bg={s['bg']}")
    return s


def print_status() -> None:
    if keeper_alive():
        print(f"caffeine: ENABLED (keeper pid {keeper_pid()} running)")
    else:
        print("caffeine: DISABLED (no keeper running)")
    t = now()
    files = sorted(STATE_DIR.glob("sess-*.json"))
    if not files:
        print("  (no active sessions)")
    for f in files:
        s = read_session(f)
        fresh = "fresh" if t < s["expiry"] else "STALE"
        left = max(0, s["expiry"] - t)
        print(f"  {f.name}: turn={s['turn']} bg={s['bg']} ({fresh}, expiry in {left}s)")
    if LOG_FILE.exists():
        print(f"  recent log ({LOG_FILE}):")
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines()[-8:]:
            print(f"    {line}")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ACTIONS:
        if sys.stderr:  # absent under pythonw
            usage = "|".join(a for a in ACTIONS if a != "__keeper")
            print(f"usage: caffeine.py [{usage}]", file=sys.stderr)
        return 1
    action = sys.argv[1]
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if action == "__keeper":
        run_keeper()
        return 0
    if action == "status":
        print_status()
        return 0

    payload = read_payload()
    sid = session_id(payload)
    path = session_file(sid)

    acquire_lock(action, sid)
    try:
        if action == "reset":  # new session: drop only this session's state
            s = read_session(path)
            log(f"reset sid={sid} dropped turn={s['turn']} bg={s['bg']}")
            path.unlink(missing_ok=True)
            stop_keeper_if_idle()
        else:
            s = transition(sid, path, action, payload)
            if action in ("on", "acquire"):
                start_keeper()
            else:
                stop_keeper_if_idle()
    finally:
        release_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
