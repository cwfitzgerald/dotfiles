## Change report store

Keep reports outside the repository. Treat the report store as persistent user
state, not as disposable temporary data.

If the harness restricts writes to this root, request access to the resolved
root. Do not fall back to the repository, a worktree, or an agent-specific
directory.

Resolve the store root in this order:

1. If `CHANGE_ANALYSIS_HOME` is set, use its value.
2. On Windows, use `LOCALAPPDATA/change-analysis`. If `LOCALAPPDATA` is not
   set, use `AppData/Local/change-analysis` below the user home directory.
3. On macOS, use `Library/Application Support/change-analysis` below the user
   home directory.
4. On Linux, use `XDG_STATE_HOME/change-analysis`. If `XDG_STATE_HOME` is not
   set, use `.local/state/change-analysis` below the user home directory.

Use native path separators. Store UTF-8 text. Limit JSON to deterministic
manifest data and helper output. Agents must write semantic handoffs as
Markdown. Generated directory names must contain only lowercase ASCII letters,
digits, and hyphens. Do not use symlinks.

The versioned layout is:

```text
<store-root>/
`-- v1/
    `-- repositories/
        `-- <repository-key>/
            `-- reports/
                `-- <report-id>/
                    |-- manifest.json
                    |-- report.md
                    |-- walkthrough-notes.md
                    |-- evidence/
                    |-- investigations/
                    |-- iterations/
                    |   `-- 001/
                    |       |-- request.md
                    |       |-- implementation.md
                    |       |-- analysis-update.md
                    |       `-- review.md
                    `-- restack-attempts/
```

Use `uv run --no-cache <skill-directory>/scripts/change_reports.py` to resolve
the root, generate a repository key, list reports, resolve a report selector,
or select the next iteration directory. The helper accepts `root`, `repo-key`,
`list`, `resolve`, and `next-iteration` subcommands. Run its `--help` option for
exact arguments. The helper uses only the Python standard library and does not
install dependencies.

The repository identity is the normalized primary remote URL. If no remote
exists, use the canonical repository root. The helper normalizes common HTTPS,
SSH, and scp-style remote forms before it generates the key.

Do not maintain a global mutable index. Find reports by scanning
`manifest.json` files below `repositories`. An exact report ID must resolve to
one report. Reject ambiguous matches. The `latest` selector requires a
repository key and selects the newest complete matching manifest.

Write manifest updates through a temporary file in the report directory, then
replace `manifest.json` atomically. Keep report file paths relative to the
report directory. Print the report ID and its absolute path whenever a command
creates or selects a report.

Each manifest has this minimum shape:

```json
{
  "schema_version": 1,
  "report_id": "pr-123-a1b2c3d4",
  "repository": {
    "key": "repository-0123456789ab",
    "identity": "example.com/owner/repository",
    "root": "/current/local/path",
    "vcs": "jj"
  },
  "source": {
    "kind": "pull-request",
    "label": "pr-123",
    "revset": "base..head",
    "base_commit_id": "...",
    "head_commit_id": "...",
    "base_tree_id": "...",
    "final_tree_id": "..."
  },
  "created_at": "2026-01-01T00:00:00Z",
  "status": "complete",
  "files": {
    "report": "report.md",
    "walkthrough_notes": "walkthrough-notes.md"
  }
}
```

Use `pull-request`, `revision-range`, or `working-copy` for `source.kind`.
Additional fields are allowed. The source final tree is the tree from the
initial analysis. After the manifest status becomes `complete`, do not change
the manifest, `report.md`, `evidence/`, or `investigations/`. Later skills may
update `walkthrough-notes.md` and add `iterations/` or `restack-attempts/`
entries.

A new subject creates a new report ID. Use the source label and a short initial
final tree ID as the base report ID, then add a numeric suffix if that directory
already exists. Revisions made from walkthrough decisions stay under the same
report ID.

## Revision iterations

Use a zero-padded numeric directory for each revision iteration. Do not reuse or
renumber an iteration. Write each file atomically. `ready`, `complete`,
`failed`, `accepted`, and `changes-requested` are terminal file statuses. Do not
change a file after it records one of those statuses. A blocked file may be
replaced atomically after the missing input becomes available.

The explainer writes `request.md` only after the user has agreed to the code
changes. Use these headings:

- `Status` with `ready` or `blocked`.
- `Input final tree`.
- `Agreed changes`.
- `Required behavior`.
- `Preserved behavior`.
- `Acceptance criteria`.
- `Required checks`.
- `Open questions`.

A ready request has no unresolved question that can change the implementation.
The implementer writes `implementation.md` with status `complete`, `failed`, or
`blocked`, plus the input and output tree IDs, changed areas, checks, and
limitations. The implementer writes `analysis-update.md` with the affected
verification and validation conclusions. This is a focused update, not a
replacement for the initial report.

The explainer writes `review.md` after it walks through the implementation
delta. Use `accepted`, `changes-requested`, or `blocked` as the status. If the
review requests more code changes, create the next iteration and put the new
ready request there.

Keep a `Status` line in `walkthrough-notes.md`. Use `in-progress`,
`revision-requested`, `complete`, or `blocked`. When the status becomes
`complete`, also record `Accepted final tree`. That tree must be the initial
final tree or the output tree of an accepted iteration.

The effective final tree is the output tree from the latest complete
implementation. If no implementation is complete, it is the initial final tree
from the manifest. The accepted final tree is the tree recorded in a complete
walkthrough. A restack requires a complete walkthrough and no later ready
request or unreviewed implementation.

Keep revisions in this report while they implement or refine decisions about
the same change. Create a new report only when the base changes or the revision
materially expands the problem, product scope, or affected architecture beyond
the evidence boundary of the initial report.
