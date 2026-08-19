---
name: spec-review
description: Review, edit, or write specification-shaped technical prose at any formality — code and doc comments, error messages, commit and PR descriptions, design docs, RFCs, API contracts, standards text. Use whenever the task is to propose changes to such text, draft a section, settle a wording question, or judge whether something is ambiguous, minimal, or consistent, including when introducing a new term or invariant into existing text or code. Applies to bare asks like "does this wording work", "tighten this", "review this comment", "is this clear".
---

# Spec review

Goal: exactly one interpretation available to a reader who cannot ask a follow-up question. Fluency is secondary and sometimes opposed — smooth text that admits two readings is worse than awkward text that admits one.

Two failure modes to fight:

1. **Diff sprawl** — a change touching more than the thing it fixes. Buries the substantive edit and destroys reviewability.
2. **Concept creep** — every term, entity, or state introduced is a permanent tax on future readers. Text accretes concepts faster than it sheds them.

## Register

Identify the register before proposing anything. The discipline is constant; the ceremony is not.

| Register | Belongs | Does not belong |
|---|---|---|
| Code comment | Why, invariants, what the reader would get wrong | Definitions, requirement keywords, restating the code |
| Doc comment / API reference | Preconditions, postconditions, errors, ownership | Rationale essays |
| Commit / PR description | What changed, what it makes true, what it does not fix | Defined terms |
| Design doc / RFC | Problem, chosen semantics, alternatives, open questions | Conformance language for unbuilt things |
| Standard / formal spec | Defined terms, requirement keywords, testable requirements | Rationale inside normative text, tutorial voice |

Invariant across registers: minimal diff, concept budget, one name per thing, the ambiguity checks. Scaling with formality: definition apparatus, requirement keywords, explicitness of attribution.

## Purpose

Establish what the document is for and who acts on it before touching anything. If that is neither stated nor inferable, that is the first finding.

Every section, sentence, and example must serve that purpose. Content serving a different purpose belongs in a different document: link it, do not host it. Recurring violations are rationale inside normative text, tutorial material in reference docs, restated code in comments, project status in design docs, and requirements for things declared out of scope.

For anything you add, name the purpose it serves. If the answer is completeness or symmetry, cut it. For anything already present that cannot be tied to the purpose, say which it is — dead weight, or evidence the stated purpose is wrong or too narrow.

The same test applies to the change itself: a change serves one purpose, and material that serves another purpose is a second change.

## Minimal diff

Change the smallest span that fixes the problem.

- Prefer editing a clause over a sentence, a sentence over a paragraph, a paragraph over a section.
- Leave working text alone. Different-and-fine is not a defect.
- Do not fix adjacent wording you read on the way to the fix. Raise it separately; the author decides whether it belongs in this change.
- Keep existing terminology, tense, voice, and section conventions, unless the inconsistency is the bug.
- If the fix seems to need a large diff, stop and say why first. Usually the diagnosis was wrong, or there is a structural issue that needs its own discussion rather than smuggling into a wording fix.

Present changes as diffs. Never hand back a rewritten passage the reader has to diff themselves.

Scope the diff to the changed span, not the enclosing sentence: break the surrounding lines so unchanged clauses sit on context lines and only the altered clause appears in `-`/`+`.

```diff
-The caller releases the buffer appropriately
+The caller must release the buffer
 before the device is destroyed.
```

not

```diff
-The caller releases the buffer appropriately before the device is destroyed.
+The caller must release the buffer before the device is destroyed.
```

Keep a whole sentence in the hunk only when the change genuinely spans it, or when line breaks carry meaning in the source format. This reflow is for reading the review; match the file's existing wrapping in anything meant to apply.

## Concept budget

Each concept introduced must pay for itself:

- **Load-bearing?** If it can be said with concepts already present, do that. A new name for an existing thing is a pure loss.
- **Referenced more than once?** A concept used once belongs inlined at its use site. Naming exists to enable reference.
- **Exactly one name?** Check the surrounding text for competing names for one thing, and one name covering different things. The second is worse and easier to miss.
- **Matches the code?** Prose naming a thing differently from the identifiers is a defect even when both names are good — the reader builds the mapping and builds it wrong.
- **Introduced before use?** Explicit forward references are fine; silent ones are not.
- **Collides with a term of art?** A term with an established meaning in the domain, a referenced document, or the implementations cannot be redefined locally.

When reviewing, name the concepts the change introduces and say whether each earns its place. Reviewers usually skip this; it is usually the most valuable part.

## Ambiguity checks

From ASD-STE100 (Simplified Technical English), built so aircraft maintenance instructions could not be misread. Diagnostics, not dogma.

- **One thing, one name.** Never vary terminology for elegance. A "buffer" is not also an "allocation" or "resource" — variation reads as a deliberate distinction to anyone who does not already know the material.
- **Noun clusters of at most three.** `descriptor set layout binding array element` has no recoverable modifier structure. Prepositions force attachment to be explicit.
- **No `-ing` form as subject or main predicate.** Gerunds conflate act, agent, and concurrent condition. *Binding the resource fails* — heading, state, or claim? Use a finite verb with an explicit subject.
- **Name the actor.** Passive drops it, and it is usually the load-bearing fact: the implementation, the runtime, the caller, or the user? "Is validated" is not a requirement until you say by whom.
- **Condition before action.** "Do X, unless Y" invites acting on the first clause; "If not Y, do X" does not. Same reason a safety comment goes above the `unsafe` block.
- **One requirement per sentence.** Compound requirements get partially implemented and partially tested. Past ~25 words, requirement text is nearly always two claims with an unstated relationship: split it and state the relationship.
- **No unbound demonstratives.** "This means…" with a whole paragraph as antecedent is ambiguous by construction. Name the thing.
- **No unquantified qualifiers.** "appropriate", "as needed", "reasonable", "sufficient", "typically", "where possible", "etc." — each hands an unresolved question to the reader. Quantify it, or say it is deliberately unspecified.
- **No `and/or`.** Say which.

## Obligations

Keep requirement-bearing text visibly separate from descriptive text; a reader must never guess whether a sentence constrains them.

Use RFC 2119 keywords if the document does; do not if it does not. Where in use: lowercase "must" is a defect, since its normativity is unclear. `MUST` for a statement of fact is a category error — a constraint on producers and a fact about the format get tested differently. `MAY` is permitted freedom, not likelihood; "might" is likelihood. Every `SHOULD` needs its escape condition, or deviation has no legitimate boundary. Prefer requirements whose violation has a nameable observable consequence; without one it is untestable.

Without keywords, get the same precision from an explicit subject, a finite verb, and a stated consequence: "Callers must hold the lock" over "the lock should be held"; "Panics if the slice is empty" over "should not be called with an empty slice".

STE would ban most requirement vocabulary. Requirement modality wins; STE governs the prose around the keywords.

## Output

Inline suggestions for code review, a findings list for a document. Either way, per finding:

1. Quote the exact span — a clause, not a section.
2. State the interpretation problem concretely. "Ambiguous" is not a review comment; "a caller could read this as validating before or after the state transition" is.
3. Propose the replacement as a minimal diff.

Severity, most severe first:

- **Interpretation risk** — two readers could act differently. Blocking.
- **Concept cost** — unearned or duplicate concept, inconsistent term, prose disagreeing with code. Blocking unless justified.
- **Clarity** — one reading available, but the reader works for it. Worth fixing.
- **Nit** — style, formatting, convention. Label it and keep it out of the way.

If the text is good, say so and stop. Padding a review with nits trains authors to skim reviews.

## Do not

- Rewrite a passage into your own voice.
- Add examples, notes, or clarifying sentences unless asked, or unless the ambiguity cannot be fixed in place. Added prose is added surface area and goes stale first.
- Delete text you do not understand. Ask what it was for — spec text and old comments often encode a hard-won constraint whose rationale lives in an issue thread.
- Change requirement strength during a wording cleanup. `SHOULD` to `MUST`, or "should" to "must", is a semantic change and must be flagged as one.
