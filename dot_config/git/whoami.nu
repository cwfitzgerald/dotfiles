# Report which identity and GitHub account the current repository resolves to.
#
# Identity is a function of where the repo lives; see .config/git/identity-*,
# .config/jj/conf.d/10-identity.toml and ~/.local/bin/gh, all generated from the
# mapping in chezmoi's .chezmoidata.toml. Because git, jj and gh each resolve the
# mapping independently, this script asks all three and screams if they disagree
# -- a disagreement means the deployed configs have drifted from the source.

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

# Which GitHub account the repo's key authenticates as.
def key-account [ssh: string]: nothing -> string {
    let r = (^sh -c $"($ssh) -o ConnectTimeout=10 -T git@github.com" | complete)
    ([$r.stdout $r.stderr] | str join "\n" | lines
        | where ($it | str starts-with "Hi ")
        | get 0? | default ""
        | parse "Hi {user}!{rest}" | get user.0? | default "")
}

# Which GitHub account `gh` acts as. Routed by ~/.local/bin/gh, which keys off
# the working directory rather than the repo's git dir. --json holds the exit
# code at 0, so a config dir with no login reads as empty rather than as a
# failure.
def gh-account []: nothing -> string {
    let r = (^gh auth status --active --json hosts --jq '.hosts."github.com"[0].login' | complete)
    if $r.exit_code != 0 { return "" }
    $r.stdout | str trim
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

    let key_user = if ($ssh | is-empty) { "" } else { key-account $ssh }

    if ($ssh | is-empty) {
        print "key:     (none - this repo is outside every configured scope)"
        print "github:  would be denied"
    } else {
        print $"key:     ($ssh | split row '-i ' | last | str trim)"
        if ($key_user | is-empty) {
            print "github:  denied"
        } else {
            print $"github:  ($key_user)"
        }
    }

    let gh_user = (gh-account)
    if ($gh_user | is-empty) {
        print "gh:      (no login in this directory's config dir)"
    } else {
        print $"gh:      ($gh_user)"
    }

    # git pushes as the key's account while `gh` acts as its own, routed by
    # separate configs. If they disagree, one of the two is aimed at the wrong
    # account for this directory.
    let accounts_agree = if (($key_user | is-empty) or ($gh_user | is-empty)) {
        true
    } else if $key_user == $gh_user {
        true
    } else {
        print $"(ansi red_bold)MISMATCH:(ansi reset) git pushes as ($key_user) but gh acts as ($gh_user)"
        print "  ~/.local/bin/gh and .config/git/identity-* disagree on this directory"
        false
    }

    if not ($in_sync and $accounts_agree) { exit 1 }
}
