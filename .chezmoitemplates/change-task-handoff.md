## Reuse role tasks

Treat the task that first ran each skill as a persistent role task. Prefer to
resume the prior analysis task for implementation work and the prior explainer
task for later walkthroughs. Do not recommend a fresh task when the relevant
prior task is available. The report is the durable fallback when the task cannot
be resumed.

If the harness can message or resume another task and the prior task is known,
offer to send the exact next invocation after the user approves that handoff.
Do not create a replacement task automatically. If task routing is unavailable,
tell the user which prior task to open and give the exact invocation.

## Segment handoff

At each phase boundary, approval checkpoint, or blocker, end with a `Segment
handoff` section containing:

- `Status`: `complete`, `waiting`, or `blocked`.
- `Completed`: one sentence that names the finished work. Use `none` when
  blocked before work completes.
- `Next job`: one concrete action.
- `Resume task`: `analysis`, `explainer`, `restack`, `this task`, or `none`.
- `Invoke`: the exact `$change-*` invocation, or `none`.

Use `complete` only when this skill's current segment is done. Use `waiting` when
the next action is an approval or an answer in the same task. Do not hide failed
checks or unresolved decisions behind a complete status.
