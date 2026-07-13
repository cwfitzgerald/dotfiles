I use `jj` for version control. You have permission to access `jj diff --git --no-pager -f <from> -t <to>`. `@` is the working directory. `trunk` is the head of the repository, whatever it is named. Unless explicitly asked, do not commit work. If explicitly asked to commit work, write terse commit messages, and never add a co-authored-by for an AI assistant. Use `jj pr-diff --git --no-pager` to diff current head against the latest commit from trunk it touches. When creating a new repository, name the default branch `trunk` (not `main`).

When operating in jj, use @ only as the working copy. Never edit a commit directly, always `jj new` to a child, then `jj squash` or `jj restore -f @ -t @- --restore-descendants` to apply the changes with/without changing dependents. Use `jj commit` (which is `jj describe` + `jj new`) when creating a commit.

When creating a worktree (`jj workspace add` or `git worktree`), place it inside the repo under `.worktrees/<name>` rather than in a sibling directory. Make sure `.worktrees/` is ignored first (add it to `.git/info/exclude` if it isn't already) so the outer workspace doesn't try to snapshot the nested worktree.

`jj` currently only supports an "ignore all LFS files" mode, so LFS-tracked files never appear in `jj st` / `jj diff`. When a repo uses Git LFS, use `git status` / `git diff` to inspect those file changes before committing.

{{ if eq .harness "codex" }}
When running `jj` commands in Codex, always use `sandbox_permissions: "require_escalated"` because `jj` needs access to home-directory configuration and state.

When running `gh` commands in Codex, always use `sandbox_permissions: "require_escalated"` because `gh` needs access outside the sandbox.
{{- end }}

Always use `cargo nextest` to run tests if the project does not have specific instructions. Favor `cargo clippy` over `cargo check`. Always use LF line endings.

Avoid the `#[path = "..."]` attribute unless there is genuinely no alternative. For sharing helper modules across Rust integration tests without generating extra test binaries, prefer `autotests = false` in `Cargo.toml` plus an explicit `[[test]]` entry, and place helper `.rs` files as siblings of the test root reached by plain `mod foo;`.

Project-local facts (testing conventions, build quirks, repo-specific workflows) belong in the project's `CLAUDE.md`/`AGENTS.md`, not in the auto-memory system. Reserve auto-memory for cross-project user/feedback facts.

I want to be in control and produce very high quality work, so ask many questions, and clarify things often.

You have access to the `gh` cli. Use it for read-only purposes, unless explicitly asked.

My global assistant config is managed by chezmoi. Shared instructions live in `~/.local/share/chezmoi/.chezmoitemplates/agent-instructions.md` and are rendered to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and `~/.pi/agent/AGENTS.md`. Claude hooks/settings are sourced from `~/.local/share/chezmoi/dot_claude/`, Codex hooks and stable config are sourced from `~/.local/share/chezmoi/dot_codex/`, and Pi agent config is sourced from `~/.local/share/chezmoi/dot_pi/`. Edit the chezmoi source and run `chezmoi apply`, or `chezmoi add <target-path>` to bring an existing target file under management. Do not hand-edit managed targets; they will drift. Chezmoi auto-commits and pushes to my dotfiles repo, so adding/editing managed files publishes them.

Any change to Claude, Codex, `jj`, or other dev-tool configuration (instructions, hooks, settings, aliases, ignore rules, etc.) must be made through chezmoi — edit the chezmoi source (or `chezmoi add` the target first) rather than the live config, so the change propagates to my other computers. If you find yourself about to hand-edit a config file that isn't yet managed by chezmoi, bring it under chezmoi management instead.
{{ if eq .harness "claude" }}
When delegating work to subagents via the Agent tool, pass an explicit `model` and match the tier to the work item's difficulty rather than defaulting everything to one model:

- `model: "opus"` for serious work and anything needing critical thinking: non-trivial implementation, debugging, design-sensitive research, architectural judgment, and fresh-eyes review.
- `model: "sonnet"` as the workhorse for moderate, well-scoped tasks: routine implementation, standard research, and code reading that needs some judgment but not deep reasoning — a good default when a task is neither hard nor trivial.
- `model: "haiku"` for cheap, fast, mechanical work whose output I can verify at a glance: running tests and reporting results, simple renames, straightforward "find where X is defined" lookups, file/state checks.
- When in doubt between two tiers, pick the higher one — a failed cheap agent costs more than a successful expensive one.
- Never use `model: "fable"` unless I explicitly ask; fable is reserved for orchestration, not delegated work.

Use `subagent_type: "Explore"` for read-only research when it fits, and `"general-purpose"` for everything else.

A subagent's `model` override is not preserved across a stall-and-resume: always re-specify the same `model` override it was originally spawned with.
{{- end }}
