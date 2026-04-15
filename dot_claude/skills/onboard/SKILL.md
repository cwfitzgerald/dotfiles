---
name: onboard
description: >
  Deeply understand a PR, changeset, or repository for review or onboarding.
  Use this skill whenever the user mentions reviewing a PR, getting onboarded
  to a change, understanding a codebase, preparing for code review, or asks
  about what a PR/changeset does. Also use when the user says "review",
  "onboard", "understand this change", or references pr-diff/jj diff in a
  review context.
---

# Code Review / Changeset Onboarding

## Purpose

Help me deeply understand a PR, changeset, or repository so I can review or
work on it effectively. I'm a graphics engineer working primarily on
GPU-related Rust codebases (wgpu, renderers, etc.), so assume familiarity
with graphics pipelines, GPU APIs, async, unsafe Rust, and systems-level
concerns.

## Inputs — determine scope from context

- **PR (checked out locally)**: Save the diff to a temp file once, then
  read from it as needed — do NOT call diff commands multiple times.
  ```
  jj pr-diff --git --no-pager > /tmp/pr-review.diff
  ```
  Use `gh pr view` and `gh pr view --comments` to pull the full PR
  description and all commentary including self-review comments.
- **PR (not checked out)**: Same approach, but fetch via `gh`:
  ```
  gh pr diff <number> > /tmp/pr-<number>.diff
  ```
- **Changeset**: Use `jj diff --git --no-pager -f <from> -t <to>` with
  the revisions specified. For large diffs, write to a temp file first.
- **Repository/subsystem**: Start from directory structure, build system,
  and key entry points.

$ARGUMENTS can specify a PR number, revision range, or subsystem path.

## Execution

### Phase 1: Gather

- Read the diff and **all** associated commentary (PR description, review
  comments, self-review inline threads). Authors leave critical reasoning
  in inline comments — don't skip them.
- Identify files changed, their roles, and dependency relationships between
  changes.
- For large diffs, spawn **foreground** sub-agents split by subsystem or
  logical concern.

### Phase 2: Synthesize — present to me

1. **Goal & motivation**: What is this change accomplishing, and why?
2. **Architecture / flow**: How does the change flow? Execution path or
   structural reorganization. Diagram if complex.
3. **Key decisions**: What design choices were made? What alternatives
   exist? Flag anything chosen for convenience over correctness.
4. **Risk areas**: Where are the likely bugs, edge cases, regressions, or
   maintenance burdens? Be adversarial — assume problems exist and find them.
5. **Testing**: What's tested, what's not, what should be? Are tests
   verifying the invariants that actually matter?
6. **Commentary summary**: Distill the PR/review discussion. What was
   debated? What's unresolved?
7. **Review order** (mandatory): Provide an ordered reading plan.
   - If the PR is structured for commit-by-commit review, list commits in
     the recommended order.
   - Otherwise, list files in the order I should read them, with a
     one-line rationale for each explaining why it belongs at that position
     (e.g., "defines the core trait other files depend on").

### Phase 3: Interactive review

- **Ask me questions** before and during. Clarify my concerns, focus areas,
  and desired depth.
- When I raise concerns, help me articulate them precisely for review
  comments.
- Be direct and upfront. Don't hedge. If something looks wrong, say so.

## Behavioral notes

- Be thorough and adversarial. Find problems before merge, not after.
- Don't summarize away detail — I need actual mechanics.
- Use foreground sub-agents for large changes to avoid losing context.
- Read-only `gh` and `jj` only. Don't commit anything.
- Over-communicate, over-question. I want to be in control and produce
  high-quality reviews.
