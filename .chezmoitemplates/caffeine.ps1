param(
    [ValidateSet("on", "off", "acquire", "release", "reset", "status")]
    [string]$Action
)

# Self-healing, multi-session keep-awake.
#
# Each agent session owns one state file under $Dir describing whether it wants
# the machine awake (a foreground turn is in progress, or background agents are
# running). A single "keeper" process re-asserts the Windows wake lock while ANY
# session wants awake, and exits (releasing the lock) once none do.
#
# State is namespaced per session, so one session's SessionStart `reset` never
# touches another's, and every event stamps a rolling expiry so a crashed
# session's stale hold is ignored and swept up automatically -- no leaked
# reference counts, no cross-session sabotage.

$Dir           = [System.IO.Path]::Combine($env:TEMP, "claude-caffeine")
$KeeperPidFile = [System.IO.Path]::Combine($Dir, "keeper.pid")
$Interval      = 60    # keeper re-check cadence, seconds
$StaleTtl      = 7200  # a hold is ignored this many seconds after its last refresh

New-Item -ItemType Directory -Path $Dir -Force | Out-Null

function Get-Now { [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }

# The session id is provided by the hook harness as JSON on stdin. Read it at
# script scope: inside a function `$input` is that function's own (empty)
# pipeline, and [Console]::In blocks on an interactive console, so only read
# when stdin is actually redirected (as it is under a hook).
$StdinRaw = ""
if ([Console]::IsInputRedirected) {
    try { $StdinRaw = [Console]::In.ReadToEnd() } catch { }
}

# Codex and manual invocations may not supply a session id; fall back to a
# shared "default" bucket.
function Get-SessionId {
    if ($StdinRaw.Trim()) {
        try {
            $j = $StdinRaw | ConvertFrom-Json
            foreach ($k in @("session_id", "sessionId", "conversation_id", "thread_id")) {
                if (($j.PSObject.Properties.Name -contains $k) -and $j.$k) {
                    return [string]$j.$k
                }
            }
        } catch { }
    }
    return "default"
}

function Get-SessionFile([string]$sid) {
    $safe = ($sid -replace '[^A-Za-z0-9_.-]', '_')
    return [System.IO.Path]::Combine($Dir, "sess-$safe.json")
}

function Read-Session([string]$file) {
    if (Test-Path $file) {
        try {
            $o = Get-Content $file -Raw -ErrorAction Stop | ConvertFrom-Json
            return [pscustomobject]@{
                turn   = [int]$o.turn
                bg     = [int]$o.bg
                expiry = [long]$o.expiry
            }
        } catch { }
    }
    return [pscustomobject]@{ turn = 0; bg = 0; expiry = [long]0 }
}

function Write-Session([string]$file, $obj) {
    $obj.expiry = (Get-Now) + $StaleTtl
    $obj | ConvertTo-Json -Compress | Set-Content -Path $file -Encoding UTF8
}

function Test-AnyWantsAwake {
    $now = Get-Now
    $files = Get-ChildItem -Path $Dir -Filter "sess-*.json" -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $s = Read-Session $f.FullName
        if (($now -lt $s.expiry) -and (($s.turn -eq 1) -or ($s.bg -gt 0))) {
            return $true
        }
    }
    return $false
}

function Get-KeeperPid {
    if (Test-Path $KeeperPidFile) {
        $raw = Get-Content $KeeperPidFile -ErrorAction SilentlyContinue
        $n = 0
        if ([int]::TryParse($raw, [ref]$n)) { return $n }
    }
    return 0
}

function Test-KeeperAlive {
    $p = Get-KeeperPid
    return ($p -gt 0) -and [bool](Get-Process -Id $p -ErrorAction SilentlyContinue)
}

function Stop-Keeper {
    $p = Get-KeeperPid
    if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
    Remove-Item $KeeperPidFile -Force -ErrorAction SilentlyContinue
}

# Stop the keeper only if nothing wants awake anymore; otherwise leave it so
# other sessions keep their lock.
function Stop-KeeperIfIdle {
    if (-not (Test-AnyWantsAwake)) { Stop-Keeper }
}

function Start-Keeper {
    if (Test-KeeperAlive) { return }

    # Baked-in values ($Dir/$KeeperPidFile/$Interval) interpolate from this
    # scope; inner-runtime variables are backtick-escaped so they stay literal.
    $keeper = @"
Add-Type -TypeDefinition '
using System;
using System.Runtime.InteropServices;
public class SleepPreventer {
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
    public const uint ES_CONTINUOUS = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED = 0x00000001;
    public const uint ES_DISPLAY_REQUIRED = 0x00000002;
}
'
`$dir     = "$Dir"
`$pidFile = "$KeeperPidFile"
while (`$true) {
    `$now   = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    `$wants = `$false
    `$files = Get-ChildItem -Path `$dir -Filter "sess-*.json" -ErrorAction SilentlyContinue
    foreach (`$f in `$files) {
        try { `$o = Get-Content `$f.FullName -Raw -ErrorAction Stop | ConvertFrom-Json } catch { continue }
        `$exp = [long]`$o.expiry
        if (`$now -ge `$exp) {
            Remove-Item `$f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        if (([int]`$o.turn -eq 1) -or ([int]`$o.bg -gt 0)) { `$wants = `$true }
    }
    if (`$wants) {
        [SleepPreventer]::SetThreadExecutionState(
            [SleepPreventer]::ES_CONTINUOUS -bor
            [SleepPreventer]::ES_SYSTEM_REQUIRED -bor
            [SleepPreventer]::ES_DISPLAY_REQUIRED) | Out-Null
    } else {
        [SleepPreventer]::SetThreadExecutionState([SleepPreventer]::ES_CONTINUOUS) | Out-Null
        Remove-Item `$pidFile -Force -ErrorAction SilentlyContinue
        break
    }
    Start-Sleep -Seconds $Interval
}
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($keeper))
    $proc = Start-Process powershell `
        -ArgumentList "-NoProfile", "-EncodedCommand", $encoded `
        -WindowStyle Hidden -PassThru
    $proc.Id | Set-Content $KeeperPidFile
}

$sid  = Get-SessionId
$file = Get-SessionFile $sid

switch ($Action) {
    # Foreground turn started: mark this session active and ensure a keeper runs.
    "on" {
        $s = Read-Session $file
        $s.turn = 1
        Write-Session $file $s
        Start-Keeper
    }
    # A background agent spawned: pin this session awake beyond the turn's end.
    "acquire" {
        $s = Read-Session $file
        $s.bg = $s.bg + 1
        Write-Session $file $s
        Start-Keeper
    }
    # A background agent finished: drop its pin; sleep once nothing else wants awake.
    "release" {
        $s = Read-Session $file
        $s.bg = [Math]::Max(0, $s.bg - 1)
        Write-Session $file $s
        Stop-KeeperIfIdle
    }
    # Foreground turn ended: clear active flag; sleep once no background agents remain.
    "off" {
        $s = Read-Session $file
        $s.turn = 0
        Write-Session $file $s
        Stop-KeeperIfIdle
    }
    # New session: drop only this session's leftover state, then release if idle.
    "reset" {
        Remove-Item $file -Force -ErrorAction SilentlyContinue
        Stop-KeeperIfIdle
    }
    # Report keeper state and every session's outstanding holds.
    "status" {
        if (Test-KeeperAlive) {
            Write-Output "caffeine: ENABLED (keeper pid $(Get-KeeperPid) running)"
        } else {
            Write-Output "caffeine: DISABLED (no keeper running)"
        }
        $now = Get-Now
        $files = Get-ChildItem -Path $Dir -Filter "sess-*.json" -ErrorAction SilentlyContinue
        if (-not $files) {
            Write-Output "  (no active sessions)"
        }
        foreach ($f in $files) {
            $s = Read-Session $f.FullName
            $fresh = if ($now -lt $s.expiry) { "fresh" } else { "STALE" }
            $left  = [Math]::Max(0, $s.expiry - $now)
            Write-Output ("  {0}: turn={1} bg={2} ({3}, expiry in {4}s)" -f $f.Name, $s.turn, $s.bg, $fresh, $left)
        }
    }
}
