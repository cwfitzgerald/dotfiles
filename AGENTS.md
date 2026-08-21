# dotfiles (chezmoi source)

This repo is the chezmoi source directory for my global configuration. Nothing here
is a live config file — everything is a *source* file that chezmoi renders into `~`.

## This repo is public

`cwfitzgerald/dotfiles` is a **public GitHub repo**, and chezmoi is configured with
`autoCommit = true` / `autoPush = true`. Any file you write here is committed and
pushed to the open internet on the next `chezmoi add` or `chezmoi re-add` — those
commit the whole source directory, not just the file named. There is no staging
area and no review step. Treat every edit as publishing.

Never write into this repo:

- My employer's name, or any client, customer, or partner name.
- Work email addresses, usernames, or coworker names.
- Internal hostnames, private IPs, VPN or intranet URLs, internal registry or
  artifact URLs, S3/GCS bucket names.
- Ticket IDs, project codenames, or repo names from private/internal orgs.
- Anything at all secret: keys, tokens, passwords, SSH private keys, session
  cookies. Public SSH keys and allowed-signers entries are fine.
- Absolute paths that embed any of the above.

Instead:

- Identity values (emails, signing keys) are **prompted** by `.chezmoi.toml.tmpl`
  and stored in `~/.config/chezmoi/chezmoi.toml`, which is *not* in this repo.
  Reference them as `.email`, `.workEmail`, `.signingKey`, `.workSigningKey`.
- Whether a machine has a work identity at all is expressed as
  `{{ if get . "workEmail" }}` — a boolean, never the value itself.
- Directory-to-identity mapping lives in `.chezmoidata.toml` as generic paths
  (`~/Programming/work`), never as employer-specific names.
- If something genuinely must differ per employer, add a prompted variable to
  `.chezmoi.toml.tmpl` rather than a literal.

When writing prose in this repo (including this file and the shared agent
instructions), say "work machine" / "work identity" rather than naming anyone.
Before committing, re-read the diff and ask whether a stranger reading it learns
anything about who I work for.

## Layout

```
.chezmoi.toml.tmpl        Config template; prompts for identity on `chezmoi init`.
.chezmoidata.toml         Static data, re-read every apply (unlike chezmoi.toml).
.chezmoiexternal.toml     Third-party content fetched from URLs (skills, archives).
.chezmoiignore            Target paths chezmoi should NOT create. Itself a template.
.chezmoitemplates/        Named partials, included via `{{ template "name" . }}`.
dot_foo/                  -> ~/.foo
readonly_Documents/       -> ~/Documents, mode 0444
AppData/, Library/        OS-specific trees, gated in .chezmoiignore.
```

Source-name attributes: `dot_` → leading `.`, `private_` → mode 0600, `readonly_`
→ mode 0444, `executable_` → +x, `symlink_` → the file's contents are the symlink
target, `.tmpl` → rendered as a Go template. They stack:
`dot_ssh/private_config.tmpl` → `~/.ssh/config`, mode 0600, templated.

Files and directories beginning with `.` are chezmoi's own and are never applied.
`README.md`, `AGENTS.md`, and `CLAUDE.md` are repo-only and are listed in
`.chezmoiignore` so they stay out of `~`.

## Per-directory identity

On a work machine, which identity a repo gets is a function of where it lives.
`.chezmoidata.toml` holds the directory → identity mapping, and three generated
consumers read it:

| Consumer | Source | Mechanism |
| --- | --- | --- |
| commit email, signing key, ssh key | `dot_gitconfig.tmpl` + `dot_config/git/identity-*` | git `includeIf "gitdir:"` |
| jj commit email, signing key | `dot_config/jj/conf.d/10-identity.toml.tmpl` | jj scopes |
| `gh` account | `dot_local/bin/executable_gh.tmpl` | wrapper on PATH, sets `GH_CONFIG_DIR` |

Work is the machine default in all three; the open-source directories are the
only override, so a repo outside the mapping gets the work identity (git, which
sets `useConfigOnly`, instead hard-errors rather than guessing). `gh`'s account
lives in `$GH_CONFIG_DIR/hosts.yml`, so routing it means picking a config dir:
`~/.config/gh` for work, `~/.config/gh-open` for open source, each authenticated
by its own `gh auth login`. `git whoami` reports what the directory you are
standing in resolves to and errors if the three disagree.

None of this is deployed on a single-identity machine; see `.chezmoiignore`.

## Workflow

Edit the source, then apply:

```
chezmoi apply -v
```

Use `chezmoi diff` first if the change is non-obvious. To bring an existing file
in `~` under management:

```
chezmoi add ~/.config/foo/bar.toml
```

**Never hand-edit a managed target.** `~/.claude/CLAUDE.md`, `~/.gitconfig`,
`~/.ssh/config`, etc. are generated; edits there are silently reverted on the next
apply. Edit the source file in this repo instead.

`chezmoi re-add` pulls target-side edits back into the source, but it **refuses to
overwrite templates**. Since almost everything here is a `.tmpl`, re-add is not a
usable path for most files — edit the source directly.

Useful for debugging templates:

```
chezmoi execute-template < .chezmoitemplates/agent-instructions.md
chezmoi cat ~/.claude/CLAUDE.md
chezmoi data
```

## Agent instructions

`.chezmoitemplates/agent-instructions.md` is the single source for my global agent
instructions. It is rendered into four targets, each passing a `harness` value:

| Target | Source | `.harness` |
| --- | --- | --- |
| `~/.claude/CLAUDE.md` | `dot_claude/CLAUDE.md.tmpl` | `claude` |
| `~/.codex/AGENTS.md` | `dot_codex/AGENTS.md.tmpl` | `codex` |
| `~/.cursor/rules/global.mdc` | `dot_cursor/rules/global.mdc.tmpl` | `cursor` |
| `~/.pi/agent/AGENTS.md` | `dot_pi/agent/AGENTS.md.tmpl` | `pi` |

Harness-specific guidance goes in a `{{ if eq .harness "..." }}` block; anything
outside those blocks reaches all four. `.chezmoitemplates/skill-oversee.md` is
shared the same way between the Claude, Codex, and Cursor `oversee` skills.

Cursor is the odd one: it loads Claude's and Codex's skills and hooks directly,
so `dot_cursor` holds only what that misses or must shadow. Read the comment in
`dot_cursor/hooks.json.tmpl` before adding an event there.

Edits to that template are edits to my instructions on every machine — keep it
tight, and keep it employer-agnostic per the rules above.

## Scope

Any change to Claude, Codex, Cursor, Pi, `jj`, git, `gh`, ssh, or shell configuration belongs
here, not in the live file. If a config file isn't managed yet, `chezmoi add` it
first, then edit the source.
