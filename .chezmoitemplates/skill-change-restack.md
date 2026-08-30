---
name: change-restack
description: >
  Plan and apply a jj commit and pull-request stack from a change-analysis
  report while preserving its accepted aggregate final tree. Use only when the
  user explicitly invokes change-restack by name.
{{- if or (eq .harness "claude") (eq .harness "cursor") }}
disable-model-invocation: true
{{- end }}
---

# Restack a change

Use an existing change report to create a reviewable jj commit and pull-request
stack. The arguments give a report ID, `latest`, or a report directory.

This skill has a mandatory proposal checkpoint. Do not change version-control
state until you have shown the concrete proposed graph and the user has approved
that proposal. Invocation alone is not approval.

Do not change the accepted aggregate final tree. Do not fix product or
implementation defects while restacking. Do not push commits, create or update
remote pull requests, or submit review comments unless the user separately
requests those actions.

{{ template "change-analysis-storage.md" . }}

## Load and check the evidence

Resolve the report and read `manifest.json`, `report.md`, relevant investigation
notes, `walkthrough-notes.md`, and every iteration file. Use `jj` as the source
of truth for the live graph. Follow all repository-specific jj instructions.

Require manifest schema version 1 and status `complete`. An exact ID or path may
identify an incomplete report; do not restack it.

Require a complete walkthrough and resolve its accepted final tree. Confirm
that this tree is the initial final tree or the output tree of an accepted
iteration. Stop if a ready request, unreviewed implementation, blocked review,
or changes-requested review is newer than the latest accepted tree. Set the next
job to the task that owns that pending segment.

Verify the base and accepted final tree IDs before planning. A graph-only
rewrite is not staleness. If the base changed or the live final tree differs
from the accepted final tree without a matching iteration record, stop and
report the mismatch. Preserve unresolved verification and validation findings
in the plan; do not hide them with a cleaner graph.

Identify unrelated working-copy changes, bookmarks, or descendants that the
rewrite could affect. If you cannot isolate them safely, stop and ask the user
how to proceed.

## Design the story and landing units

A pull request is one atomic landing unit. For every proposed pull request, the
aggregate change relative to its parent pull request must:

- Form one coherent change.
- Pass the repository's required CI-equivalent checks.
- Contain all implementation, tests, migrations, and integration needed for its
  stated purpose.
- Have no hidden dependency on a descendant pull request.

Stacked pull requests may depend on their parent pull requests. State each such
dependency.

Commits inside a pull request do not need to compile, pass tests, or land by
themselves. Each commit must still add one useful proposition to the story. A
reader who processes commits in order must learn something new at each step.

Prefer commit boundaries that expose concepts, behavior, or deliberate
transitions. Mechanical commits are acceptable when separating the operation
makes review easier; explain that reason. Do not create cleanup commits whose
only purpose is to repair an avoidable defect in an earlier commit.

## Propose before mutation

Show the user:

- The current graph.
- The proposed commit and pull-request graph.
- The purpose and atomic landing claim for each pull request.
- The proposition introduced by each commit.
- Dependencies between commits and pull requests.
- Commits that are expected not to compile or pass tests.
- The required checks at each pull-request tip.
- The mapping from current commits to proposed commits.
- Difficult file or hunk movements and any ambiguity in their ownership.
- How you will prove that the accepted aggregate final tree is unchanged.

Wait for explicit approval of this proposal. If feedback changes the graph,
show the revised proposal and ask for approval again.

At this checkpoint, use a waiting segment handoff. The next job is for the user
to approve or revise the proposal in this restack task. Do not name another
skill invocation.

## Apply the approved proposal

After approval:

1. Record the current jj operation ID, graph, bookmarks, base tree, and accepted
   final tree below a new `restack-attempts/` directory in the report.
2. Work from a new jj child or isolated workspace as required by repository
   instructions. Do not edit a historical commit directly.
3. Construct replacement commits and local bookmarks without touching
   unrelated changes or descendants.
4. Keep the original graph reachable until the user accepts the result.
5. Prove that the replacement parent tree equals the recorded base tree and the
   replacement tip tree equals the accepted final tree. Equivalently, prove
   equality of the complete base-to-tip diff. Any difference is a failure. Stop
   and repair the restack operation, not the code.
6. Run the required checks at every proposed pull-request tip. Individual
   commits do not require checks.
7. Write the resulting graph, old-to-new commit mapping, check results, and tree
   comparison below the attempt directory.
8. Present the result for review before removing recovery references or moving
   any published bookmark.

Do not claim that a pull request is landable when a required check failed or was
not run. State the exact limitation.

## Iterate

The user may refine ordering, boundaries, commit messages, or pull-request
grouping after an applied attempt. Repeat the propose, approve, and apply cycle.
Every attempt must preserve the accepted aggregate final tree.

If the user wants to change product behavior or fix code, stop the restack loop.
Set the next job to resume the explainer task. The explainer records the agreed
change in a new iteration request before the analysis task implements it.

Finish when the user accepts the local graph. Report the final pull-request
stack, commit story, checks, tree-equality evidence, recovery information,
report ID, and absolute report path. Do not push unless separately requested.
Set the next job to the user's chosen bookmark, push, or pull-request operation,
or to none when the local graph is the requested endpoint.

{{ template "change-task-handoff.md" . }}
