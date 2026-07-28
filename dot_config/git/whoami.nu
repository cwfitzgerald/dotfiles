# Report which identity and GitHub account the current repository resolves to.
#
# Identity is a function of where the repo lives; see .config/git/identity-*
# and .config/jj/conf.d/10-identity.toml, both generated from the mapping in
# chezmoi's .chezmoidata.toml. Because git and jj each resolve the mapping
# independently, this script asks both and screams if they disagree -- a
# disagreement means the deployed configs have drifted from the source.

# Three states worth telling apart, because they mean very different things:
#   in_repo = false          -> not in a repo; nothing to resolve yet
#   in_repo, git_dir = ""    -> plain or colocated repo, `git config` works
#   in_repo, git_dir = path  -> non-colocated jj repo, whose git dir lives
#                               under .jj and still matches the includeIf rules
def repo-context []: nothing -> record<in_repo: bool, in_jj: bool, git_dir: string> {
    let in_git = (^git rev-parse --git-dir | complete).exit_code == 0
    let root = (^jj root | complete)
    let in_jj = $root.exit_code == 0
    if $in_git {
        return {in_repo: true, in_jj: $in_jj, git_dir: ""}
    }
    if not $in_jj {
        return {in_repo: false, in_jj: false, git_dir: ""}
    }
    let candidate = ([($root.stdout | str trim) ".jj" "repo" "store" "git"] | path join)
    if ($candidate | path exists) {
        {in_repo: true, in_jj: true, git_dir: $candidate}
    } else {
        {in_repo: true, in_jj: true, git_dir: ""}
    }
}

def git-cfg [dir: string, key: string]: nothing -> string {
    let r = if ($dir | is-empty) {
        ^git config $key | complete
    } else {
        ^git --git-dir $dir config $key | complete
    }
    if $r.exit_code == 0 { $r.stdout | str trim } else { "" }
}

def jj-cfg [key: string]: nothing -> string {
    let r = (^jj config get $key | complete)
    if $r.exit_code == 0 { $r.stdout | str trim } else { "" }
}

# git and jj resolve the same directory->identity mapping through separate
# configs; if they ever disagree, one of the generated files is stale.
def check-sync [what: string, git_val: string, jj_val: string]: nothing -> bool {
    if $git_val == $jj_val { return true }
    print $"(ansi red_bold)MISMATCH:(ansi reset) git and jj resolve different ($what)s"
    print $"  git: '($git_val)'"
    print $"  jj:  '($jj_val)'"
    print "  the generated configs have drifted; run `chezmoi status` / `chezmoi apply`"
    false
}

let ctx = (repo-context)

if not $ctx.in_repo {
    # Standing in a container directory such as ~/Programming/work is the
    # common case here. The scopes match repositories *under* those paths, so
    # there is nothing to resolve until you are inside one.
    print "not in a git or jj repository"
    print "identity resolves per-repository, so run this inside a clone"
} else {
    let email = (git-cfg $ctx.git_dir "user.email")
    let name = (git-cfg $ctx.git_dir "user.name")
    let signing_key = (git-cfg $ctx.git_dir "user.signingkey")
    let ssh = (git-cfg $ctx.git_dir "core.sshCommand")

    let in_sync = if $ctx.in_jj {
        [
            (check-sync "commit email" $email (jj-cfg "user.email"))
            (check-sync "signing key" $signing_key (jj-cfg "signing.key"))
        ] | all { $in }
    } else {
        true
    }

    if ($email | is-empty) {
        print "commit:  (none - this repo is outside every configured scope)"
    } else {
        print $"commit:  ($name) <($email)>"
    }

    if ($ssh | is-empty) {
        print "key:     (none - this repo is outside every configured scope)"
        print "github:  would be denied"
    } else {
        print $"key:     ($ssh | split row '-i ' | last | str trim)"
        let r = (^sh -c $"($ssh) -o ConnectTimeout=10 -T git@github.com" | complete)
        let out = ([$r.stdout $r.stderr] | str join "\n")
        let hi = ($out | lines | where ($it | str starts-with "Hi ") | get 0? | default "")
        if ($hi | is-empty) {
            print "github:  denied"
        } else {
            print $"github:  ($hi | parse 'Hi {user}!{rest}' | get user.0)"
        }
    }

    if not $in_sync { exit 1 }
}
