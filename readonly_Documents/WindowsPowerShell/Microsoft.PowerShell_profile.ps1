# PowerShell profile — managed by chezmoi

# fnm (Fast Node Manager)
# fnm supports PowerShell natively; --use-on-cd installs the cd hook and the
# multishell junction that PATH points at, so version switching is automatic.
if (Get-Command fnm -ErrorAction SilentlyContinue) {
    fnm env --use-on-cd | Out-String | Invoke-Expression
}
