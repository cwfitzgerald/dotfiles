# Forget a non-default jj workspace and remove its directory.
def main [
    workspace: string # Workspace name, as shown by `jj workspace list`
] {
    if $workspace == "default" {
        error make { msg: "Refusing to remove the default workspace." }
    }

    # Resolve the path before forgetting the workspace, since jj removes this
    # metadata. jj cannot resolve a recorded path once its directory is gone.
    let root_result = (^jj workspace root --name $workspace | complete)
    let root_missing = (
        ($root_result.stderr | str contains "Cannot resolve absolute workspace path")
        and (
            ($root_result.stderr | str contains "(os error 2)")
            or ($root_result.stderr | str contains "(os error 3)")
        )
    )
    let workspace_root = if $root_result.exit_code == 0 {
        $root_result.stdout | str trim | path expand
    } else if $root_missing {
        null
    } else {
        error make { msg: ($root_result.stderr | str trim) }
    }

    if $workspace_root != null {
        let workspace_repo = ($workspace_root | path join ".jj" "repo")
        if ($workspace_repo | path exists) and (($workspace_repo | path type) == "dir") {
            error make {
                msg: "Refusing to remove the primary workspace, which owns the jj repository store."
            }
        }
    }

    let current_root_result = (^jj workspace root | complete)
    if $current_root_result.exit_code != 0 {
        error make { msg: ($current_root_result.stderr | str trim) }
    }
    let current_root = ($current_root_result.stdout | str trim | path expand)
    if $workspace_root != null and $workspace_root == $current_root {
        error make {
            msg: "Refusing to remove the current workspace. Run this command from another workspace."
        }
    }

    let forget_result = (^jj workspace forget $workspace | complete)
    if $forget_result.exit_code != 0 {
        error make { msg: ($forget_result.stderr | str trim) }
    }

    if $workspace_root == null {
        print $"Forgot workspace '($workspace)'; its directory was already absent or could not be resolved."
    } else if ($workspace_root | path exists) {
        rm --recursive $workspace_root
        print $"Forgot workspace '($workspace)' and removed ($workspace_root)."
    } else {
        print $"Forgot workspace '($workspace)'; ($workspace_root) was already absent."
    }
}
