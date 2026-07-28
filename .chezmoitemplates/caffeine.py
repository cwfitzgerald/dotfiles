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
through a SubagentStart acquire (hidden housekeeping agents, resumed agents),
so blind decrements drain holds belonging to still-running work. Stop and
SubagentStop payloads carry an authoritative `background_tasks` list, so those
events *reconcile* bg from it instead of doing arithmetic; the acquire counter
only bridges the gap between an agent spawn and the next reconciling event.

Ending a turn is not one event. Stop is documented not to fire on a user
interrupt, and an API error fires StopFailure in its place, so `off` is also
wired to StopFailure, to the `idle_prompt` Notification, and to
PostToolUseFailure via `interrupt` (which acts only on `is_interrupt`). Without
those, an Esc pins the machine awake until the hold expires. Conversely,
SessionStart fires on `compact` and `fork` *mid-turn*, so `reset` ignores those
sources rather than dropping a live hold.

Both harnesses share this script and this state dir, and both name the same
SessionStart sources, so one keeper covers the machine. They diverge on what
exists: Codex has no Notification, StopFailure or PostToolUseFailure, so it
gets no interrupt signal and falls back to SessionEnd plus the expiry. Its
Stop/SubagentStop payloads also omit `background_tasks`, so bg there is the
arithmetic path -- sound only because Codex fires SubagentStop solely for the
ThreadSpawn agents that fired SubagentStart.

Wake backends: SetThreadExecutionState on Windows, caffeinate(8) on macOS.
Elsewhere the keeper only tracks state and logs a warning.

Stdlib only, and hooks must invoke it via pythonw on Windows: a console-
subsystem interpreter spawned by a console-less hook harness allocates a
visible console window on every event.

Targets Python 3.8: macOS ships 3.9 as /usr/bin/python3 and the hooks run under
whatever `python3` resolves to, so `X | None` annotations must stay deferred.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(tempfile.gettempdir()) / "claude-caffeine"
KEEPER_PID_FILE = STATE_DIR / "keeper.pid"
LOG_FILE = STATE_DIR / "caffeine.log"
PAYLOAD_LOG_FILE = STATE_DIR / "hookdebug.log"
LOCK_DIR = STATE_DIR / ".lock"

INTERVAL = 60  # keeper re-check cadence, seconds
STALE_TTL = 7200  # a hold is ignored this many seconds after its last refresh
KEEPER_BEAT_TTL = 300  # a keeper whose heartbeat is older than this is not ours
LOG_ROTATE_BYTES = 1_000_000

ACTIONS = (
    "on",
    "off",
    "acquire",
    "release",
    "touch",
    "interrupt",
    "reset",
    "status",
    "__keeper",
)

# SessionStart sources that really mean "fresh session". `compact` and `fork`
# fire mid-turn against a session that is still working.
RESET_SOURCES = ("startup", "clear", "resume")


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


def write_atomic(path: Path, text: str) -> None:
    """The keeper and `status` read these files without taking the lock, and a
    torn read parses as {turn:0, bg:0} -- which reads as "nobody wants awake"
    and drops the wake lock mid-turn. Swap the file in whole instead."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def write_session(path: Path, state: dict) -> None:
    state["expiry"] = now() + STALE_TTL
    write_atomic(path, json.dumps(state))


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


def read_keeper_record() -> tuple:
    """(pid, last heartbeat epoch). A bare-integer file is the pre-heartbeat
    format; report beat=0 for it."""
    try:
        raw = KEEPER_PID_FILE.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return 0, 0
    try:
        rec = json.loads(raw)
        return int(rec["pid"]), int(rec["beat"])
    except (ValueError, TypeError, KeyError):
        pass
    try:
        return int(raw), 0
    except ValueError:
        return 0, 0


def write_keeper_record(pid: int) -> None:
    write_atomic(KEEPER_PID_FILE, json.dumps({"pid": pid, "beat": now()}))


def keeper_pid() -> int:
    return read_keeper_record()[0]


def keeper_alive() -> bool:
    """A live pid alone is not proof: the state dir outlives a reboot on
    Windows, where the OS is free to reissue the recorded pid to something
    unrelated. Requiring a warm heartbeat keeps us from mistaking a stranger
    for the keeper -- and, in stop_keeper, from sending it a SIGTERM."""
    pid, beat = read_keeper_record()
    if not pid_exists(pid):
        return False
    return now() - beat < KEEPER_BEAT_TTL


def clear_keeper_record(pid: int) -> None:
    """Only when it still names us. A keeper that overran its heartbeat may
    have been superseded, and deleting the successor's record would have the
    next hook spawn a third."""
    if keeper_pid() == pid:
        KEEPER_PID_FILE.unlink(missing_ok=True)


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
    write_keeper_record(proc.pid)
    log(f"keeper-start pid={proc.pid}")


def stop_keeper() -> None:
    if keeper_alive():
        pid = keeper_pid()
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
        elif sys.platform == "darwin":
            if self.caffeinate is not None and self.caffeinate.poll() is not None:
                # Killed out from under us; hold() is the re-assert point.
                log("keeper-warn caffeinate died; respawning")
                self.caffeinate = None
            if self.caffeinate is None:
                # -w ties the assertion to the keeper's lifetime, even if killed.
                try:
                    self.caffeinate = subprocess.Popen(
                        ["caffeinate", "-dis", "-w", str(os.getpid())]
                    )
                except OSError as e:
                    log(f"keeper-warn caffeinate unavailable: {e}")

    def drop(self) -> None:
        if os.name == "nt":
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        elif self.caffeinate is not None:
            self.caffeinate.terminate()
            try:  # reap, so a keeper that later re-holds leaves no zombie
                self.caffeinate.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.caffeinate.kill()
            self.caffeinate = None


def sweep() -> bool:
    """Drop expired holds; report whether any survivor still wants awake."""
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
    return wants


def run_keeper() -> None:
    me = os.getpid()
    wake = WakeLock()
    while True:
        try:
            wants = sweep()
        except OSError as e:
            # Err toward staying awake: a transient stat failure is a much
            # cheaper mistake than sleeping the machine mid-turn.
            log(f"keeper-warn sweep failed: {e}")
            wants = True
        if not wants:
            # Exit under the lock. Otherwise a hook can see us alive, skip
            # start_keeper, and be left with no keeper the moment we return.
            acquire_lock("__keeper", str(me))
            try:
                if not any_wants_awake():
                    wake.drop()
                    log("keeper-exit (idle)")
                    clear_keeper_record(me)
                    return
            finally:
                release_lock()
        wake.hold()
        write_keeper_record(me)  # heartbeat: proves this pid is still ours
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
    elif action == "interrupt":  # a tool failed; only Esc ends the turn
        if payload.get("is_interrupt"):
            s["turn"] = 0
    elif action == "touch":  # tool activity: renew the expiry, change nothing
        pass
    write_session(path, s)
    log(f"{action} sid={sid} {prev} -> turn={s['turn']} bg={s['bg']}")
    return s


def print_status() -> None:
    pid, beat = read_keeper_record()
    if keeper_alive():
        print(f"caffeine: ENABLED (keeper pid {pid}, beat {now() - beat}s ago)")
    elif pid:
        print(f"caffeine: DISABLED (stale record for pid {pid}, no live keeper)")
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
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines()[-8:]:
            print(f"    {line}")


def dispatch() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ACTIONS:
        if sys.stderr:  # absent under pythonw
            usage = "|".join(a for a in ACTIONS if a != "__keeper")
            print(f"usage: caffeine.py [{usage}]", file=sys.stderr)
        return 1
    action = sys.argv[1]
    # 0o700: on Linux the temp dir is shared, and these files carry prompt text.
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

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
        source = payload.get("source")
        if action == "reset" and source is not None and source not in RESET_SOURCES:
            # SessionStart also fires for `compact` and `fork`, which happen
            # partway through a turn that is still running. Resetting there
            # drops the hold during exactly the long turns worth protecting.
            log(f"reset-skip sid={sid} source={source}")
        elif action == "reset":  # new session: drop only this session's state
            s = read_session(path)
            log(f"reset sid={sid} source={source} turn={s['turn']} bg={s['bg']}")
            path.unlink(missing_ok=True)
            stop_keeper_if_idle()
        else:
            s = transition(sid, path, action, payload)
            if action in ("on", "acquire"):
                start_keeper()
            elif action == "touch":
                # Every tool call doubles as a self-heal point for a keeper
                # that died while its session still wanted awake.
                if s["turn"] == 1 or s["bg"] > 0:
                    start_keeper()
            else:
                stop_keeper_if_idle()
    finally:
        release_lock()
    return 0


def main() -> int:
    try:
        return dispatch()
    except Exception:
        # A keep-awake hiccup must never surface as a hook error in the
        # transcript, and must never exit 2 -- that erases a submitted prompt
        # on UserPromptSubmit and blocks the turn from ending on Stop.
        # dispatch() releases the lock in its own finally, and releasing one we
        # do not hold would rmdir another process's lock.
        try:
            log("error " + " | ".join(traceback.format_exc().strip().splitlines()))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
