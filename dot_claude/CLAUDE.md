I use `jj` for version control. You have permission to access `jj diff --git --no-pager -f <from> -t <to>`. `@` is the working directory. `trunk` is the head of the repository, whatever it is named. Unless explicitly asked, do not commit work. If explicitly asked to commit work, write terse commit messages, and never add a co-authored-by for claude. Use `jj pr-diff --git --no-pager` to diff current head against the latest commit from trunk it touches.

`jj` currently only supports an "ignore all LFS files" mode, so LFS-tracked files never appear in `jj st` / `jj diff`. When a repo uses Git LFS, use `git status` / `git diff` to inspect those file changes before committing.

Always use `cargo nextest` to run tests if the project does not have specific instructions. Favor `cargo clippy` over `cargo check`. Always use LF line endings.

Avoid the `#[path = "..."]` attribute unless there is genuinely no alternative. For sharing helper modules across Rust integration tests without generating extra test binaries, prefer `autotests = false` in `Cargo.toml` plus an explicit `[[test]]` entry, and place helper `.rs` files as siblings of the test root reached by plain `mod foo;`.

Project-local facts (testing conventions, build quirks, repo-specific workflows) belong in the project's `CLAUDE.md`, not in the auto-memory system. Reserve auto-memory for cross-project user/feedback facts.

I want to be in control and produce very high quality work, so ask many questions, and clarify things often.

You have access to the `gh` cli. Use it for read-only purposes, unless explicitly asked.

Always use foreground agents, or else you will get permissions issues.
