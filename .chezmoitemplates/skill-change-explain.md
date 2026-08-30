---
name: change-explain
description: >
  Present a change-analysis report as an interactive technical story and record
  the reader's corrections, decisions, and preferred narrative. Use only when
  the user explicitly invokes change-explain by name.
{{- if or (eq .harness "claude") (eq .harness "cursor") }}
disable-model-invocation: true
{{- end }}
---

# Explain a change

Present one existing change report as an interactive story. The arguments give
a report ID, `latest`, or a report directory. On later invocations for the same
report, continue the existing walkthrough and review only new implementation
iterations. Do not restart completed chapters.

Do not edit source files or version-control state. You may inspect referenced
source when the user asks a precise follow-up question.

{{ template "change-analysis-storage.md" . }}

## Load and check the report

Resolve the report selector. When the selector is `latest`, derive the current
repository key first. Read `manifest.json`, `report.md`, relevant investigation
notes, existing `walkthrough-notes.md`, and every iteration file.

Require manifest schema version 1 and status `complete`. An exact ID or path may
identify an incomplete report; do not explain it.

Older walkthrough notes may not have a `Status` or `Accepted final tree` line.
Do not repeat their completed chapters. Reconstruct the state from recorded user
decisions. If those decisions contain agreed code changes, create the next ready
request and mark the walkthrough `revision-requested`.

Verify that the referenced repository and jj objects still exist. Determine the
effective final tree from the iteration records. Do not require the current
working copy to be at the base or effective final tree. A changed commit graph
is acceptable when the base and effective final trees are unchanged. Use a
restack mapping when one is available, but do not require one.

If the live change has a different final tree and no complete implementation
records that tree, explain the mismatch and stop. Set the next job to resume the
analysis task and resolve the unrecorded change. Do not request a new full
analysis for a recorded iteration.

Treat the report as evidence, not as authority. Preserve its confidence labels
and unresolved questions. When source evidence contradicts the report, record
the correction and identify the affected claim.

## Walk through the story

Start with a short orientation, a chapter list, and the first chapter. Do not
dump the complete report or ask whether to begin.

Use this default order, but adapt it when another order teaches the change more
clearly:

1. The problem and why it matters.
2. The minimum system context needed to understand the problem.
3. Relevant behavior before the change.
4. The first new idea.
5. Each later idea and its dependence on earlier ideas.
6. Resulting behavior and important preserved behavior.
7. Verification findings.
8. Validation findings.
9. The candidate commit and pull-request story.

Present one chapter at a time. Each chapter states:

- The new claim.
- Why the claim matters.
- The relevant before-and-after behavior.
- The implementation path and evidence locations.
- Important risks, uncertainty, or questions.

Define project-local terms at first use. Assume general technical knowledge but
no implicit knowledge of the feature, prior author discussion, or repository
history. Use stable terminology. Do not vary names for style.

When the user interrupts with a question, answer it at the requested depth and
then return to the current place in the story. Distinguish the implementation's
behavior from your judgment about that behavior.

## Review an implementation delta

If the latest complete implementation has no `review.md`, do not repeat the
initial walkthrough. Present only:

- The agreed request.
- The implementation delta and its behavioral effect.
- The focused verification and validation update.
- Check results and limitations.
- Initial conclusions or story decisions that the delta changes.

Ask only the questions needed to decide whether the iteration is accepted. If
the user accepts it, write `review.md` with status `accepted`, record its output
as the accepted final tree, and mark the walkthrough complete. If the user wants
more code changes, write status `changes-requested`, then create the next
iteration's ready `request.md` and mark the walkthrough `revision-requested`.
If a required decision is missing, write status `blocked` and record the exact
question.

## Record the walkthrough

Keep `report.md` immutable. Update `walkthrough-notes.md` with:

- Chapters completed.
- User corrections to facts or inferred intent.
- Questions asked and conclusions reached.
- Decisions about verification and validation findings.
- The user's preferred story, commit boundaries, and pull-request boundaries.
- Remaining questions.

Keep its review status and accepted final tree consistent with the iteration
contract. Use `revision-requested` after you create a ready request. Use
`complete` only when the user has accepted the current effective final tree and
no further code decision remains.

Attribute user decisions explicitly. Do not convert an unanswered question into
a decision. Write updates atomically.

## Request implementation

When the walkthrough produces agreed code changes, use `next-iteration` to
select the directory and write `request.md` in Markdown. Do not ask the user to
repeat the decisions in a freeform implementation prompt. Create a ready request
only when its required behavior, preserved behavior, acceptance criteria, and
required checks are clear. Invocation of `change-explain` does not authorize
source changes.

After a ready request exists, this explainer segment is complete. Set the next
job to resume the original analysis task and invoke
`$change-implement <report-id>`. After implementation, the user should resume
this same explainer task and invoke `$change-explain <report-id>` for the delta.

If no code change is required and the walkthrough decisions are complete,
record the accepted final tree, mark the walkthrough complete, and set the next
job to `$change-restack <report-id>`. At each segment end, summarize
the agreed story, unresolved verification and validation findings, and the
decisions that later skills must honor. Print the report ID and absolute report
path.

{{ template "change-task-handoff.md" . }}
