# Format every commit between trunk and the current branch tip.
#
# For each commit (oldest to newest), creates a temporary working copy,
# runs the formatter, and squashes the result back into the original commit.
#
# Usage:
#   jj fmt-branch                    # defaults to `cargo fmt`
#   jj fmt-branch -- deno fmt        # custom formatter
def main [...command: string] {
    let cmd = if ($command | is-empty) { ["cargo", "fmt"] } else { $command }

    # Get all commits from trunk to branch tip, oldest first.
    # Change IDs are stable across rebases so we can collect upfront.
    let commits = (
        jj log --no-pager --no-graph -r 'trunk()..@ ~ empty()' --template 'change_id.short() ++ "\n"' --reversed
        | lines
        | where { $in != "" }
    )

    if ($commits | is-empty) {
        print "No commits to format."
        return
    }

    let total = ($commits | length)
    print $"Formatting ($total) commits with `($cmd | str join ' ')`..."

    for item in ($commits | enumerate) {
        let change_id = $item.item
        let idx = $item.index + 1

        # Show progress
        let desc = (jj log --no-pager --no-graph -r $change_id --template 'description.first_line()' --limit 1 | str trim)
        print $"  [($idx)/($total)] ($change_id) ($desc)"

        # Create temporary working copy on top of this commit
        jj new $change_id --no-pager

        # Run the formatter
        run-external ($cmd | first) ...($cmd | skip 1)

        # Squash formatting changes into the commit, rebasing descendants
        jj restore -f @ -t @- --restore-descendants --no-pager
    }

    print "Done."
}
