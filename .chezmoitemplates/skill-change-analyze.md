---
name: change-analyze
description: >
  Analyze a large pull request, jj revision range, or working-copy change and
  create a persistent evidence-backed review case for later explanation,
  implementation, and restacking. Use only when the user explicitly invokes
  change-analyze by name.
{{- if or (eq .harness "claude") (eq .harness "cursor") }}
disable-model-invocation: true
{{- end }}
---

# Analyze a change

Analyze the requested change. Produce a durable report that supports later
iterations and remains useful when this task cannot be resumed. The arguments
identify the pull request, jj revision range, or working-copy change. If the
subject is not clear from the arguments and repository state, ask the user to
identify it.

Do not edit source files, rewrite commits, move bookmarks, push changes, or
submit review comments. You may run read-only inspection and non-destructive
verification commands. Follow repository instructions for all commands.

Use `jj` as the source of truth for the local commit graph. For a pull request,
use available read-only GitHub tools to collect its description, linked problem
context, review discussion, and CI state. Record any context that is not
available. Do not infer a product requirement from implementation code alone.

{{ template "change-analysis-storage.md" . }}

## Establish the evidence boundary

Record the exact source before detailed analysis:

- Repository identity and root.
- Source kind and user-facing label.
- Original revset.
- Base and head commit IDs.
- Base and final tree IDs.
- Current commit graph and pull-request boundaries, if any.
- Dirty working-copy state.
- Product context sources that were available.

Create the report directory and an incomplete manifest before you delegate
work. Mark the manifest complete only after the primary report is complete.

## Investigate with bounded subagents

Use subagents when the harness supports them and the change has independent
areas that benefit from separate context. Otherwise perform the same work
serially.

First inspect enough of the whole change to identify its concerns. Then assign
bounded questions. Split by behavior, subsystem, or review concern. Do not split
by arbitrary file counts. Do not ask two agents to perform the same complete
review.

Useful assignments include:

- Trace an important behavior from entry point to side effect.
- Check one subsystem for correctness, failure behavior, and compatibility.
- Assess tests and compare them with the behavior they claim to verify.
- Reconstruct the user problem and challenge whether the design solves it.
- Build the commit and dependency graph.
- Perform a fresh-eyes pass after the first model of the change exists.

Each assignment must state the exact source revisions, the questions to answer,
and the required evidence format. Ask for distilled claims with file and line
references, commit IDs, commands, risks, and unknowns. Do not ask for file dumps
or a summary of the entire change. Supporting agents return their reports to the
coordinator. The coordinator writes each report below `investigations/`. A
supporting agent may write its assigned file directly only when it already has
access to the report store.

The coordinating agent owns the synthesis. Check important subagent claims
against primary evidence. Preserve disagreements and uncertainty.

## Evaluate verification and validation

Keep these reviews separate.

Verification asks whether the implementation correctly produces its stated
behavior. Check at least:

- Control flow, state transitions, and data flow.
- Error, cancellation, concurrency, and cleanup paths that are relevant.
- Compatibility and migration behavior.
- Tests, assertions, fixtures, and untested behavior.
- Unused abstraction, duplicated logic, scope drift, and generated-code
  artifacts that do not match repository conventions.

Validation asks whether the stated behavior is the correct change for the
problem. Check at least:

- The user or system problem and the evidence that it exists.
- Whether the design addresses the root cause.
- Whether scope, abstraction, and user-visible behavior match the problem.
- Important alternatives and tradeoffs.
- Whether the change solves a different or broader problem than requested.

If product context is missing, mark validation as blocked or low confidence.
If the missing context can materially change the conclusion, ask the user for
it before you finalize the report. Continue independent investigation while you
wait when the harness permits this. State what evidence or user decision is
needed. Do not convert uncertainty into approval.

For each finding, state the claim, impact, confidence, and evidence. Separate
observed facts, inferences, and recommendations. Rank material findings before
minor clarity issues.

## Build the report

Write `report.md` as an index, not as a transcript. Include:

1. Source identity and freshness data.
2. Purpose, non-goals, and product context.
3. Relevant behavior before and after the change.
4. A subsystem, file, type, interface, and data-flow map.
5. The current commit and dependency graph.
6. Verification findings.
7. Validation findings.
8. Test and CI evidence, including checks not run.
9. Risks, unknowns, and conflicting interpretations.
10. A candidate narrative: the ideas introduced in a useful reading order.
11. Candidate commit and pull-request boundaries, with known constraints.
12. An evidence index into source files, commits, commands, and investigation
    notes.

Explain local concepts when they first appear. Assume the reader has general
technical knowledge but no private feature or repository context.

Stop when every material changed subsystem has a stated purpose, behavioral
path, dependency relationship, verification status, validation status, and
evidence reference, or is listed as an unresolved question.

The initial analysis segment is complete when the report status is `complete`.
Keep this task available. If the walkthrough later produces a ready revision
request, the user should resume this analysis task and invoke
`$change-implement <report-id>` here.

Finish by printing the report ID, absolute report path, analyzed revset, base
and initial final tree IDs, and the most important unresolved questions. Do not
present the full walkthrough; `change-explain` owns that task. Set the next job
to `$change-explain <report-id>` in the explainer task.

{{ template "change-task-handoff.md" . }}
