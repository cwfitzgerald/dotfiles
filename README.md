# dotfiles
 
Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).
 
## Setup
 
```
chezmoi init cwfitzgerald
chezmoi diff
chezmoi apply -v
```

## Claude Code cloud sessions

`cloud-setup.sh` sets up a cloud session. It installs chezmoi, applies only the
agent configuration, and installs cargo-nextest. Set the setup script of the
cloud environment to:

```
#!/bin/bash
set -euo pipefail
git clone https://github.com/cwfitzgerald/dotfiles.git ~/.local/share/chezmoi
DOTFILES_EMAIL='<email>' \
DOTFILES_SIGNING_KEY='<public key>' \
  ~/.local/share/chezmoi/cloud-setup.sh
```
