# PowerShell profile — managed by chezmoi

# fnm (Fast Node Manager)
if (Get-Command fnm -ErrorAction SilentlyContinue) {
    fnm env --use-on-cd | Out-String | Invoke-Expression
}
