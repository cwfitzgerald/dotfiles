# PowerShell profile — managed by chezmoi

# fnm (Fast Node Manager)
if (Get-Command fnm -ErrorAction SilentlyContinue) {
    fnm env --use-on-cd | Out-String | Invoke-Expression

    # On Windows, fnm's per-shell multishell junction is unexecutable here: its
    # junction print-name carries a raw \??\ NT-namespace prefix that
    # CreateProcess rejects ("The system cannot find the path specified"), even
    # though the path resolves fine. So we resolve the junction chain to the
    # real install dir and put THAT (not the junction) on PATH.
    function global:__Fnm-Resolve {
        param([string]$p)
        for ($i = 0; $i -lt 8 -and $p; $i++) {
            $item = Get-Item -LiteralPath $p -ErrorAction SilentlyContinue
            if (-not $item) { return $null }
            $t = $item.Target
            if (-not $t) { return $p }
            if ($t -is [array]) { $t = $t[0] }
            $p = $t
        }
        return $p
    }

    function global:__Fnm-FixPath {
        if (-not $env:FNM_MULTISHELL_PATH) { return }
        $real = __Fnm-Resolve $env:FNM_MULTISHELL_PATH
        if (-not $real -or -not (Test-Path -LiteralPath (Join-Path $real 'node.exe'))) { return }
        $verRoot = Join-Path $env:FNM_DIR 'node-versions'
        $kept = $env:PATH -split ';' | Where-Object {
            $_ -and $_ -ne $real -and -not $_.StartsWith($verRoot, [System.StringComparison]::OrdinalIgnoreCase)
        }
        $env:PATH = (@($real) + $kept) -join ';'
    }

    # fnm's use-on-cd defines Set-FnmOnLoad (called by its `cd` alias). Re-define
    # it to also re-point PATH after every activation, and fix PATH once now.
    function global:Set-FnmOnLoad {
        if ((Test-Path .nvmrc) -or (Test-Path .node-version) -or (Test-Path package.json)) {
            & fnm use --silent-if-unchanged
        }
        __Fnm-FixPath
    }
    __Fnm-FixPath
}
