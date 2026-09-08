I want to be in control and produce very high quality work, so ask many questions, and clarify things often.

# Code Style

All complexity needs to be worth its keep. Do not introduce complexity unless explicitly cleared with me. We are not strictly optimizing for a minimal diff, but every additional bit of complexity needs to justified. If pure code motion would make the codebase or future changes easier to understand, they should be their own commit.

# Writing

You MUST write in simple technical english from ASD-STE100. When writing comments, you are expected be prudent. You should add comments as needed to fields, structs, functions, other items, and modules. Item and field comments should be terse one to two lines. Only document arguments if the behavior is non-obvious. Module comments should be a one sentence header and a supporting paragraph, if justified. You are always documenting _the current state_ of the system and not comparing to any previous state. The bar for adding inline comments in code is much higher as most comments are redundant with the code. You should not remove existing comments if not asked for.

# Rust

Always use `cargo nextest` to run tests if the project does not have specific instructions. Use `cargo clippy` unless you _just_ need to check if something compiles. Use `cargo fmt` for formatting. 

Avoid the `#[path = "..."]` attribute unless there is genuinely no alternative. For sharing helper modules across Rust integration tests without generating extra test binaries, prefer `autotests = false` in `Cargo.toml` plus an explicit `[[test]]` entry, and place helper `.rs` files as siblings of the test root reached by plain `mod foo;`.

# Python

Python 3 is installed and you have access to uv for project/script management.

# Projects

DO NOT use auto-memory ever. Project-local facts (testing conventions, build quirks, repo-specific workflows) belong in the project's `CLAUDE.md`/`AGENTS.md`. If something needs to be preserved globally, put it in my global tooling.

# Version Control

I use `jj` for version control. You have permission to access `jj`. `@` is the working directory and is what git sees as the working dir. You must always use `--no-pager` with jj. `trunk` is the head of the repository, whatever it is named. Unless explicitly asked, do not commit work. If explicitly asked to commit work, write terse commit messages, and never add a co-authored-by for an AI assistant. Use ``  When creating a new repository, name the default branch `trunk` (not `main`). Use `` to view a file from a specific commit.

When operating in jj, use @ only as the working copy. Never edit a commit directly, always `jj new` to a child, then `jj squash` or `jj restore -f @ -t @- --restore-descendants` to apply the changes with/without changing dependents. Use `jj commit` (which is `jj describe` + `jj new`) when creating a commit.

Useful jj commands:
- `jj log --summary` prints which files were modified for each commit.
- `jj log --stat` prints the LOC stats as well in git form.
- `jj file show -r <change_id> <file>` prints 
- `jj diff --git -f <from> -t <to>` diffs `<from>` and `<to>`. You must always use `--git` for diffs.
- `jj pr-diff --git` to diff current head against the latest commit from trunk it touches.

When creating a workspace (might be referred to as worktree) (`jj workspace add`), place it inside the repo under `.worktrees/<name>` rather than in a sibling directory. Importantly jj workspaces are _not_ git worktrees and you _cannot_ use git commands in them. I have global configuration where this is configured to always be ignored. Use `jj ws-rm <name>` to remove a workspace and delete it in one swoop.

`jj` currently only supports an "ignore all LFS files" mode, so LFS-tracked files never appear in `jj st` / `jj diff`. When a repo uses Git LFS, use `git status` / `git diff` to inspect those file changes before committing.

All commits made should pass linting and formatting. To run a command on every commit, use `jj run -r <revset> <command> <arg...>`. Each arg is passed through one at a time. If you need a shell, you must invoke the shell yourself.

# Local Tooling

You have access to the `gh` cli. Use it for read-only purposes, unless explicitly asked.
{{ if get . "workEmail" }}
I have two GitHub accounts, and a wrapper on `PATH` routes `gh` to the one that matches the directory you are working in — work by default, the open-source account under the open-source directories. So change accounts by working in the right repo, never with `gh auth switch` or `GH_CONFIG_DIR`. `git whoami` reports which identity and account the current directory resolves to.
{{ end }}
My global configuration — agent instructions, hooks, settings, `jj`/git/ssh/shell config — is managed by chezmoi, with its source at `~/.local/share/chezmoi`. Files under `~` like `~/.claude/CLAUDE.md` or `~/.gitconfig` are generated; hand-edits there are reverted on the next apply.

So: any change to Claude, Codex, Cursor, Pi, `jj`, or other dev-tool configuration must go through chezmoi rather than the live file, and if you find yourself about to hand-edit a config file that isn't managed yet, bring it under chezmoi first. To do either, work in `~/.local/share/chezmoi` and follow that repo's `AGENTS.md`, which covers the layout, the workflow, and the constraints on what may be written there.

If you have been told things about tooling which turn out not to be true, please raise it to the me instead of silently working around it. I expect all of this to be true.

# Harness Instructions

{{ if eq .harness "codex" }}
The following commands ALWAYS require `sandbox_permissions: "require_escalated"`:
- `jj`
- `gh`
- Any `cargo` that invokes rustc/clippy (due to the compilation cache).

Never give feedback through the built-in PR review system. Give all review feedback in the task conversation.

When asked to use subagents, be prudent with their use. Subagents excel at a few different areas:
- Reviews
- Exploration (they can summarize the state of the world without poluting your context)
- Parallel implementation.

When delegating work to subagents, pass an explicit `model` and `reasoning_effort` when the spawn tool supports an override, and match both to the work item's difficulty rather than defaulting everything to one configuration. These are loose guidelines.

- `model: "gpt-6-astra"` with `reasoning_effort: "low"` as your default. Astra is extremely efficient token-per-task so for any kind of thinking start here. For really tough jobs, you can elevate to `medium` or `high` as needed.
- `model: "gpt-5.6-terra"` with `reasoning_effort: "medium"` for read-heavy think-light tasks. Doing research without thinking, doing large amounts of reading. If a task must chew through tokens inherently, use terra.

Always set `fork_turns` to `"none"`. We want subagents to be able to think independently of the root context. 
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
{{- if eq .harness "cursor" }}
Cursor leaves a subagent's `model` at `inherit` unless I ask otherwise; this is me asking. When delegating work with the Task tool, pass an explicit `model` and match the tier to the work item's difficulty rather than defaulting everything to one model. The tiers below name a model family, not a slug — take the matching slug off the list the Task tool gives you.

- `opus` for serious work and anything needing critical thinking: non-trivial implementation, debugging, design-sensitive research, architectural judgment, and fresh-eyes review.
- `sol` as the workhorse for moderate, well-scoped tasks: routine implementation, standard research, and code reading that needs some judgment but not deep reasoning — a good default when a task is neither hard nor trivial.
- `composer` for cheap, fast, mechanical work whose output I can verify at a glance: running tests and reporting results, simple renames, straightforward "find where X is defined" lookups, file/state checks.
- When in doubt between two tiers, pick the higher one — a failed cheap agent costs more than a successful expensive one.
- Never use `fable` unless I explicitly ask; fable is reserved for orchestration, not delegated work.

Use `subagent_type: "explore"` for read-only research when it fits, and `"generalPurpose"` for everything else.
{{- end }}
