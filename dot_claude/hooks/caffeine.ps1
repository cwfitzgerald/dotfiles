param(
    [ValidateSet("on", "off", "acquire", "release", "reset")]
    [string]$Action,
    [int]$TimeoutMinutes = 90
)

$PidFile   = [System.IO.Path]::Combine($env:TEMP, "claude-caffeine.pid")
$CountFile = [System.IO.Path]::Combine($env:TEMP, "claude-caffeine.count")

# Reference count of in-flight background agents. The machine must stay awake
# while this is > 0, even after the main-loop turn has ended (Stop), because a
# background agent keeps running and re-invokes the main loop when it finishes.
function Get-Count {
    if (Test-Path $CountFile) {
        $raw = Get-Content $CountFile -ErrorAction SilentlyContinue
        $n = 0
        if ([int]::TryParse($raw, [ref]$n)) { return $n }
    }
    return 0
}

function Set-Count([int]$n) {
    if ($n -lt 0) { $n = 0 }
    $n | Set-Content $CountFile
}

function Stop-Caffeine {
    if (Test-Path $PidFile) {
        $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($existingPid) {
            Stop-Process -Id ([int]$existingPid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Start-Caffeine {
    # Kill existing to refresh the timeout window
    Stop-Caffeine

    $seconds = $TimeoutMinutes * 60
    $script = @"
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
[SleepPreventer]::SetThreadExecutionState(
    [SleepPreventer]::ES_CONTINUOUS -bor
    [SleepPreventer]::ES_SYSTEM_REQUIRED -bor
    [SleepPreventer]::ES_DISPLAY_REQUIRED
) | Out-Null
Start-Sleep -Seconds $seconds
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    $proc = Start-Process powershell `
        -ArgumentList "-NoProfile", "-EncodedCommand", $encoded `
        -WindowStyle Hidden -PassThru
    $proc.Id | Set-Content $PidFile
}

switch ($Action) {
    # Foreground turn started: keep awake and refresh the safety window.
    "on" {
        Start-Caffeine
    }
    # A background agent spawned: pin awake and refresh the safety window.
    "acquire" {
        Set-Count ((Get-Count) + 1)
        Start-Caffeine
    }
    # A background agent finished: release its pin, sleep only once none remain.
    "release" {
        $n = (Get-Count) - 1
        Set-Count $n
        if ($n -le 0) { Stop-Caffeine }
    }
    # Foreground turn ended: sleep only if no background agents are still running.
    "off" {
        if ((Get-Count) -le 0) { Stop-Caffeine }
    }
    # New session: clear any count leaked from a crashed prior session.
    "reset" {
        Set-Count 0
        Stop-Caffeine
    }
}
