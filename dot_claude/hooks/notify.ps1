param($Message = "Task completed", $SoundType = "default")

$Project = "Claude Code"
try {
    $gitRoot = git rev-parse --show-toplevel 2>$null
    if ($gitRoot) { $Project = Split-Path $gitRoot -Leaf }
} catch {}

$Wav = switch ($SoundType) {
    "input"    { "C:\Windows\Media\Windows Exclamation.wav" }
    "complete" { "C:\Windows\Media\tada.wav" }
    default    { "C:\Windows\Media\chimes.wav" }
}

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$balloon = New-Object System.Windows.Forms.NotifyIcon
$balloon.Icon = [System.Drawing.SystemIcons]::Information
$balloon.BalloonTipTitle = $Project
$balloon.BalloonTipText = $Message
$balloon.Visible = $true
$balloon.ShowBalloonTip(5000)

(New-Object System.Media.SoundPlayer $Wav).PlaySync()
Start-Sleep -Milliseconds 500
$balloon.Dispose()
