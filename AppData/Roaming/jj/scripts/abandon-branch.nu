def main [--revision (-r): string = "@"] {
    let revset = $"::($revision) & ~ '::trunk()'"

    jj log --no-pager -r $revset

    let answer = (input "Abandon these revisions? [Y/n] " | str trim | str downcase)

    if $answer in ["", "y", "yes"] {
        jj abandon -r $revset
    } else {
        print "Aborted."
    }
}
