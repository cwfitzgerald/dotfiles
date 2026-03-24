param(
    [ValidateSet("on", "off")]
    [string]$Action,
    [int]$TimeoutMinutes = 30
)

$PidFile = [System.IO.Path]::Combine($env:TEMP, "claude-caffeine.pid")

function Stop-Caffeine {
    if (Test-Path $PidFile) {
        $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($existingPid) {
            Stop-Process -Id ([int]$existingPid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

switch ($Action) {
    "on" {
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
    "off" {
        Stop-Caffeine
    }
}
