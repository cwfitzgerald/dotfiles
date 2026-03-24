# config.nu
#
# Installed by:
# version = "0.103.0"
#
# This file is used to override default Nushell settings, define
# (or import) custom commands, or run any other startup tasks.
# See https://www.nushell.sh/book/configuration.html
#
# This file is loaded after env.nu and before login.nu
#
# You can open this file in your default editor using:
# config nu
#
# See `help config nu` for more options
#
# You can remove these comments if you want or leave
# them for future reference.
$env.config.buffer_editor = ["code.cmd", "--wait"]
$env.config.show_banner = false

# Claude Code wrapper that fetches OAuth token from 1Password before invocation
def --wrapped claude [...args: string] {
    $env.CLAUDE_CODE_OAUTH_TOKEN = (^op read "op://Private/Claude Code API Token/credential")
    ^claude ...$args
}

# Update all important winget packages
def update-all [] {
    winget import -i ($nu.default-config-dir | path join "vcpkg.json")
}
