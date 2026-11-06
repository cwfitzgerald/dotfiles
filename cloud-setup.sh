#!/usr/bin/env bash
# Set up a Claude Code cloud session from this repo.
#
# The setup script of the cloud environment clones this repo to
# ~/.local/share/chezmoi and runs this script. The identity values are not in
# this public repo, so the setup script gives them in DOTFILES_EMAIL and
# DOTFILES_SIGNING_KEY.
set -euo pipefail

: "${DOTFILES_EMAIL:?DOTFILES_EMAIL is not set}"
: "${DOTFILES_SIGNING_KEY:?DOTFILES_SIGNING_KEY is not set}"

# The templates read this to select the cloud configuration.
export CLAUDE_CODE_REMOTE=true

bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "$bin_dir"

# A cloud session has no TTY, so each prompt in .chezmoi.toml.tmpl must have a
# value here, keyed on the exact prompt text. The work email is blank.
"$bin_dir/chezmoi" init \
  --promptString "Open-source email address=$DOTFILES_EMAIL" \
  --promptString "Open-source SSH public key (e.g. ssh-ed25519 AAAA...)=$DOTFILES_SIGNING_KEY" \
  --promptString "Work email address (blank if this machine has only one identity)="
"$bin_dir/chezmoi" apply ~/.claude ~/.agents

curl -fsSL https://get.nexte.st/latest/linux | tar zxf - -C "${CARGO_HOME:-$HOME/.cargo}/bin"
