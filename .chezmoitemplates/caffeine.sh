#!/bin/bash
# Self-healing, multi-session keep-awake (macOS sibling of caffeine.ps1).
#
# Each agent session owns one state file under $DIR describing whether it wants
# the machine awake (a foreground turn is in progress, or background agents are
# running). A single "keeper" process holds a caffeinate(8) assertion while ANY
# session wants awake, and exits (releasing the assertion) once none do.
#
# State is namespaced per session, so one session's SessionStart `reset` never
# touches another's, and every event stamps a rolling expiry so a crashed
# session's stale hold is ignored and swept up automatically -- no leaked
# reference counts, no cross-session sabotage.

ACTION="${1:-status}"

DIR="${TMPDIR:-/tmp}/claude-caffeine"
KEEPER_PID_FILE="$DIR/keeper.pid"
INTERVAL=60    # keeper re-check cadence, seconds
STALE_TTL=7200 # a hold is ignored this many seconds after its last refresh

mkdir -p "$DIR"

now() { date +%s; }

# The session id is provided by the hook harness as JSON on stdin. Only read
# when stdin is actually redirected (as it is under a hook); reading an
# interactive terminal would block.
STDIN_RAW=""
if [ ! -t 0 ]; then
    STDIN_RAW=$(cat 2>/dev/null)
fi

# Manual invocations may not supply a session id; fall back to a shared
# "default" bucket.
get_session_id() {
    local key val
    for key in session_id sessionId conversation_id thread_id; do
        val=$(printf '%s' "$STDIN_RAW" |
            sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
        if [ -n "$val" ]; then
            printf '%s' "$val"
            return
        fi
    done
    printf 'default'
}

session_file() {
    local safe
    safe=$(printf '%s' "$1" | tr -c 'A-Za-z0-9_.-' '_')
    printf '%s/sess-%s.json' "$DIR" "$safe"
}

# json_int <file> <key> -> integer value, 0 if missing/unparsable
json_int() {
    local v
    v=$(sed -n 's/.*"'"$2"'":\(-\{0,1\}[0-9][0-9]*\).*/\1/p' "$1" 2>/dev/null | head -n 1)
    printf '%s' "${v:-0}"
}

# write_session <file> <turn> <bg> -- stamps a fresh rolling expiry
write_session() {
    printf '{"turn":%d,"bg":%d,"expiry":%d}\n' "$2" "$3" "$(( $(now) + STALE_TTL ))" > "$1"
}

any_wants_awake() {
    local t f turn bg expiry
    t=$(now)
    for f in "$DIR"/sess-*.json; do
        [ -f "$f" ] || continue
        turn=$(json_int "$f" turn)
        bg=$(json_int "$f" bg)
        expiry=$(json_int "$f" expiry)
        if [ "$t" -lt "$expiry" ] && { [ "$turn" -eq 1 ] || [ "$bg" -gt 0 ]; }; then
            return 0
        fi
    done
    return 1
}

keeper_pid() {
    local p
    p=$(cat "$KEEPER_PID_FILE" 2>/dev/null)
    case "$p" in
        '' | *[!0-9]*) printf '0' ;;
        *) printf '%s' "$p" ;;
    esac
}

keeper_alive() {
    local p
    p=$(keeper_pid)
    [ "$p" -gt 0 ] && kill -0 "$p" 2>/dev/null
}

stop_keeper() {
    local p
    p=$(keeper_pid)
    if [ "$p" -gt 0 ]; then
        kill "$p" 2>/dev/null
    fi
    rm -f "$KEEPER_PID_FILE"
}

# Stop the keeper only if nothing wants awake anymore; otherwise leave it so
# other sessions keep their assertion.
stop_keeper_if_idle() {
    any_wants_awake || stop_keeper
}

start_keeper() {
    keeper_alive && return
    nohup bash "$0" __keeper </dev/null >/dev/null 2>&1 &
    printf '%s\n' $! > "$KEEPER_PID_FILE"
}

run_keeper() {
    local t f wants turn bg expiry
    # caffeinate holds the wake assertion (display + idle + system sleep) for
    # exactly as long as this keeper process lives, even if it is killed.
    caffeinate -dis -w $$ &
    while true; do
        t=$(now)
        wants=0
        for f in "$DIR"/sess-*.json; do
            [ -f "$f" ] || continue
            expiry=$(json_int "$f" expiry)
            if [ "$t" -ge "$expiry" ]; then
                rm -f "$f"
                continue
            fi
            turn=$(json_int "$f" turn)
            bg=$(json_int "$f" bg)
            if [ "$turn" -eq 1 ] || [ "$bg" -gt 0 ]; then
                wants=1
            fi
        done
        if [ "$wants" -eq 0 ]; then
            rm -f "$KEEPER_PID_FILE"
            break
        fi
        sleep "$INTERVAL"
    done
}

# Parallel agent spawns fire concurrent hooks that race on the same session
# file's read-modify-write; serialize actions under a mkdir lock (macOS has no
# flock). After ~10s of waiting, steal the lock -- hook actions finish in
# milliseconds, so an old lock means its holder crashed.
LOCK_DIR="$DIR/.lock"
lock_acquire() {
    local tries=0
    until mkdir "$LOCK_DIR" 2>/dev/null; do
        tries=$((tries + 1))
        if [ "$tries" -ge 200 ]; then
            rm -rf "$LOCK_DIR"
            tries=0
        fi
        sleep 0.05
    done
    trap 'rm -rf "$LOCK_DIR"' EXIT
}

SID=$(get_session_id)
FILE=$(session_file "$SID")

case "$ACTION" in
    on | acquire | release | off | reset) lock_acquire ;;
esac

case "$ACTION" in
    # Foreground turn started: mark this session active and ensure a keeper runs.
    on)
        write_session "$FILE" 1 "$(json_int "$FILE" bg)"
        start_keeper
        ;;
    # A background agent spawned: pin this session awake beyond the turn's end.
    acquire)
        write_session "$FILE" "$(json_int "$FILE" turn)" "$(( $(json_int "$FILE" bg) + 1 ))"
        start_keeper
        ;;
    # A background agent finished: drop its pin; sleep once nothing else wants awake.
    release)
        bg=$(( $(json_int "$FILE" bg) - 1 ))
        if [ "$bg" -lt 0 ]; then bg=0; fi
        write_session "$FILE" "$(json_int "$FILE" turn)" "$bg"
        stop_keeper_if_idle
        ;;
    # Foreground turn ended: clear active flag; sleep once no background agents remain.
    off)
        write_session "$FILE" 0 "$(json_int "$FILE" bg)"
        stop_keeper_if_idle
        ;;
    # New session: drop only this session's leftover state, then release if idle.
    reset)
        rm -f "$FILE"
        stop_keeper_if_idle
        ;;
    # Internal: the sweep loop spawned by start_keeper.
    __keeper)
        run_keeper
        ;;
    # Report keeper state and every session's outstanding holds.
    status)
        if keeper_alive; then
            echo "caffeine: ENABLED (keeper pid $(keeper_pid) running)"
        else
            echo "caffeine: DISABLED (no keeper running)"
        fi
        t=$(now)
        found=0
        for f in "$DIR"/sess-*.json; do
            [ -f "$f" ] || continue
            found=1
            turn=$(json_int "$f" turn)
            bg=$(json_int "$f" bg)
            expiry=$(json_int "$f" expiry)
            if [ "$t" -lt "$expiry" ]; then fresh="fresh"; else fresh="STALE"; fi
            left=$(( expiry - t ))
            if [ "$left" -lt 0 ]; then left=0; fi
            echo "  $(basename "$f"): turn=$turn bg=$bg ($fresh, expiry in ${left}s)"
        done
        if [ "$found" -eq 0 ]; then
            echo "  (no active sessions)"
        fi
        ;;
    *)
        echo "usage: caffeine.sh {on|off|acquire|release|reset|status}" >&2
        exit 1
        ;;
esac
