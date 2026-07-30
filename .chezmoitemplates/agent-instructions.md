I want to be in control and produce very high quality work, so ask many questions, and clarify things often.

# Rust

Always use `cargo nextest` to run tests if the project does not have specific instructions. Use `cargo clippy` unless you _just_ need to check if something compiles. Use `cargo fmt` for formatting. 

Avoid the `#[path = "..."]` attribute unless there is genuinely no alternative. For sharing helper modules across Rust integration tests without generating extra test binaries, prefer `autotests = false` in `Cargo.toml` plus an explicit `[[test]]` entry, and place helper `.rs` files as siblings of the test root reached by plain `mod foo;`.

# Python

Python 3 is installed and you have access to uv for project/script management.

# Projects

Project-local facts (testing conventions, build quirks, repo-specific workflows) belong in the project's `CLAUDE.md`/`AGENTS.md`, not in the auto-memory system. Reserve auto-memory for cross-project user/feedback facts.

# Version Control

I use `jj` for version control. You have permission to access `jj diff --git --no-pager -f <from> -t <to>`. `@` is the working directory. `trunk` is the head of the repository, whatever it is named. Unless explicitly asked, do not commit work. If explicitly asked to commit work, write terse commit messages, and never add a co-authored-by for an AI assistant. Use `jj pr-diff --git --no-pager` to diff current head against the latest commit from trunk it touches. When creating a new repository, name the default branch `trunk` (not `main`).

When operating in jj, use @ only as the working copy. Never edit a commit directly, always `jj new` to a child, then `jj squash` or `jj restore -f @ -t @- --restore-descendants` to apply the changes with/without changing dependents. Use `jj commit` (which is `jj describe` + `jj new`) when creating a commit.

When creating a workspace (aka worktree) (`jj workspace add`), place it inside the repo under `.worktrees/<name>` rather than in a sibling directory. I have global configuration where this is configured to always be ignored. Use `jj ws-rm <name>` to remove a workspace and delete it in one swoop.

`jj` currently only supports an "ignore all LFS files" mode, so LFS-tracked files never appear in `jj st` / `jj diff`. When a repo uses Git LFS, use `git status` / `git diff` to inspect those file changes before committing.

All commits made should pass linting and formatting. To run a command on every commit, use `jj run -r <revset> <command> <arg...>`. Each arg is passed through one at a time. If you need a shell, you must invoke the shell yourself.

# Local Tooling

You have access to the `gh` cli. Use it for read-only purposes, unless explicitly asked.

My global configuration — agent instructions, hooks, settings, `jj`/git/ssh/shell config — is managed by chezmoi, with its source at `~/.local/share/chezmoi`. Files under `~` like `~/.claude/CLAUDE.md` or `~/.gitconfig` are generated; hand-edits there are reverted on the next apply.

So: any change to Claude, Codex, Pi, `jj`, or other dev-tool configuration must go through chezmoi rather than the live file, and if you find yourself about to hand-edit a config file that isn't managed yet, bring it under chezmoi first. To do either, work in `~/.local/share/chezmoi` and follow that repo's `AGENTS.md`, which covers the layout, the workflow, and the constraints on what may be written there.

# Harness Instructions

{{ if eq .harness "codex" }}
The following commands ALWAYS require `sandbox_permissions: "require_escalated"`:
- `jj`
- `gh`

When delegating work to subagents, pass an explicit `model` and `reasoning_effort` when the spawn tool supports an override, and match both to the work item's difficulty rather than defaulting everything to one configuration:

- `model: "gpt-5.6-sol"` with `reasoning_effort: "high"` for serious work and anything needing critical thinking: non-trivial implementation, debugging, design-sensitive research, architectural judgment, and fresh-eyes review. Use `"xhigh"` for the hardest unusually subtle tasks.
- `model: "gpt-5.6-terra"` with `reasoning_effort: "medium"` as the workhorse for moderate, well-scoped tasks: routine implementation, standard research, and code reading that needs some judgment but not deep reasoning.
- `model: "gpt-5.6-terra"` with `reasoning_effort: "low"` for cheap, fast, mechanical work whose output I can verify at a glance: running tests and reporting results, simple renames, straightforward "find where X is defined" lookups, and file/state checks.
- When in doubt between two configurations, pick the more capable model or higher effort — a failed cheap agent costs more than a successful expensive one.

Model or effort overrides require a limited-context fork: set `fork_turns` to `"none"` or a positive turn count. A full-history fork (`fork_turns: "all"` or omitted) inherits the parent model and effort; use that when the subagent needs the complete conversation more than it needs a different configuration.
{{- end }}
{{ if eq .harness "claude" }}
When delegating work to subagents via the Agent tool, pass an explicit `model` and match the tier to the work item's difficulty rather than defaulting everything to one model:

- `model: "opus"` for serious work and anything needing critical thinking: non-trivial implementation, debugging, design-sensitive research, architectural judgment, and fresh-eyes review.
- `model: "sonnet"` as the workhorse for moderate, well-scoped tasks: routine implementation, standard research, and code reading that needs some judgment but not deep reasoning — a good default when a task is neither hard nor trivial.
- `model: "haiku"` for cheap, fast, mechanical work whose output I can verify at a glance: running tests and reporting results, simple renames, straightforward "find where X is defined" lookups, file/state checks.
- When in doubt between two tiers, pick the higher one — a failed cheap agent costs more than a successful expensive one.
- Never use `model: "fable"` unless I explicitly ask; fable is reserved for orchestration, not delegated work.

Use `subagent_type: "Explore"` for read-only research when it fits, and `"general-purpose"` for everything else.

If you are Fable, do not re-trigger a subagent if it gets stuck, it will resume as Fable.
{{- end }}
