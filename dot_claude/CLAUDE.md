I use `jj` for version control. You have permission to access `jj diff --git --no-pager -f <from> -t <to>`. `@` is the working directory. `'trunk()'` (quotes important) is the head of the repository, whatever it is named. Unless explicitly asked, do not commit work.

Always use `cargo nextest` to run tests if the project does not have specific instructions. Favor `cargo clippy` over `cargo check`. Always use LF line endings.

I want to be in control and produce very high quality work, so ask many questions, and clarify things often.

You have access to the `gh` cli. Use it for read-only purposes, unless explicitly asked.

Always use foreground agents, or else you will get permissions issues.
