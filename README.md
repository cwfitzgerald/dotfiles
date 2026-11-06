# dotfiles
 
Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).
 
## Setup
 
```
chezmoi init cwfitzgerald
chezmoi diff
chezmoi apply -v
```

## Claude Code cloud sessions

A cloud session has no TTY, so every prompt in `.chezmoi.toml.tmpl` must be
given with `--promptString`, keyed on the exact prompt text. Give the work email
prompt even when it is blank. Only the agent configuration is applied there.

```
chezmoi init cwfitzgerald --promptString "Open-source email address=<email>,Open-source SSH public key (e.g. ssh-ed25519 AAAA...)=<public key>,Work email address (blank if this machine has only one identity)="
chezmoi apply ~/.claude ~/.agents
```
