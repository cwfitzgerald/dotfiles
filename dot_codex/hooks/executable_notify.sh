#!/bin/bash
# macOS sibling of notify.ps1: desktop notification + completion sound.

MESSAGE="${1:-Task completed}"
SOUND_TYPE="${2:-default}"

PROJECT="Claude Code"
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$GIT_ROOT" ]; then
    PROJECT=$(basename "$GIT_ROOT")
fi

case "$SOUND_TYPE" in
    input)    SOUND="/System/Library/Sounds/Sosumi.aiff" ;;
    complete) SOUND="/System/Library/Sounds/Glass.aiff" ;;
    *)        SOUND="/System/Library/Sounds/Ping.aiff" ;;
esac

# Pass message/title as argv so quoting in either can't break the script.
osascript \
    -e 'on run argv' \
    -e 'display notification (item 1 of argv) with title (item 2 of argv)' \
    -e 'end run' \
    "$MESSAGE" "$PROJECT"

afplay "$SOUND"
