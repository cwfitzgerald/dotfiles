---
name: change-implement
description: >
  Implement code revisions that the user approved during a change-explain
  walkthrough, then record focused analysis and check results in the same
  review case. Use only when the user explicitly invokes change-implement by
  name.
{{- if or (eq .harness "claude") (eq .harness "cursor") }}
disable-model-invocation: true
{{- end }}
---

# Implement an agreed change

Implement the latest ready revision request in an existing change report. The
arguments give a report ID, `latest`, or a report directory. Prefer to run this
skill in the task that created the initial analysis so that it can reuse its
code and product context. The report remains the source of truth when that task
cannot be resumed.

Invocation authorizes only the source and test changes in the ready request. It
does not authorize a restack, bookmark move, push, pull-request update, or
review submission.

{{ template "change-analysis-storage.md" . }}

## Load the request

Resolve the report and read the initial report, investigation notes,
walkthrough notes, and every iteration file. Select the latest `request.md`
whose status is `ready` and which has no terminal `implementation.md`. Reject
an ambiguous state.

Verify that the live base tree is the report base tree and that the live final
tree equals the request's input final tree. A graph-only rewrite is acceptable.
Stop if unrelated working-copy changes, bookmarks, or descendants make the
implementation unsafe to isolate.

Do not implement a blocked request. If a ready request still permits two
materially different behaviors, stop and set the next job to the explainer task
with the exact decision it must obtain.

## Implement the request

Follow repository instructions and use `jj` as the source of truth. Work in the
existing working-copy commit, a new child, or an isolated workspace as those
instructions require. Do not edit a historical commit directly.

Implement each agreed change and its required tests. Preserve every stated
behavior and constraint. Do not include unrelated cleanup or broaden the
product decision. If a necessary implementation detail is not specified, use
the narrowest design that satisfies the request and record the choice.

Run the required checks plus any focused check needed for changed behavior. A
failed required check is a limitation, not a complete implementation.

## Update the analysis

Inspect the complete delta from the request input tree to the implementation
output tree. Re-evaluate the verification and validation findings affected by
that delta. Check nearby control flow, error behavior, compatibility, and tests
when the implementation can affect them.

Use bounded subagents for independent affected areas or a fresh-eyes check when
the harness supports them. Do not repeat the complete initial analysis. If the
revision materially escapes the initial evidence boundary, stop and recommend a
new `change-analyze` report instead of pretending that a focused update is
enough.

Write `implementation.md` and `analysis-update.md` in the request iteration.
Use Markdown. Record the exact input and output tree IDs, changed behavior,
changed files or subsystems, commands and results, remaining risks, and the
verification and validation conclusions that changed or stayed unresolved.

The implementation segment is complete only when both files have terminal
content and every required check has passed. Then set the next job to resume the
existing explainer task and invoke `$change-explain <report-id>`. The explainer
must review only this implementation delta.

{{ template "change-task-handoff.md" . }}
