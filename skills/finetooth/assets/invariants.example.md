# Project invariants — a sample of the structure

⚠️ This is a **sample of the form**, not of the content. The real invariants file consists of
the rules of your project, derived from what you have already paid for. Generic words are
useless here: "the code must be correct" does not help the agent tell a finding from a nitpick.

The file is pasted into the prompt of every review agent and decides what it will count as a
defect. Keep it short: the details go in the architectural decisions and the project's root instructions.

## Context that changes how findings are judged

The section most often forgotten — and it flips half the verdicts.

- **Is there a production and old data.** If there are no users yet, then "it will break
  existing links" and "that is how it was in old records" stop being a justification for
  loosening a check: it is the data that gets fixed, not the check.
- **Target scale.** Queries and lists are judged by the load you are heading for, not
  today's.
- **What must not be broken under any circumstances**, and what, on the contrary, can still
  be reworked freely.
- **Attitude to half-measures.** If a compromise fix "so it works for now" is itself
  considered a finding — say so plainly, otherwise the fixer will pick the cheap one.

## Rules that must not be broken

One item per rule. A good rule is checkable and explains the reason:

1. **The direction of dependencies between layers** — which layer may not import which, and
   what guards it (a linter, an architecture test, review).
2. **Transaction boundaries** — what must happen inside it and what outside, and how a
   deliberate exception is marked.
3. **A single write path** — if writes must go through one place, name it. A second road
   found by the agent is a finding, even if it works today.
4. **The permission check is where the data is**, not where the button is.
5. **What counts as user input** and where it must be neutralized.

For every rule it is useful to state **where it came from**: a link to a decision, to an
incident analysis or to a finding of a past review. A rule with a history is not argued
with; a rule without one is debated anew every time.

## What is NOT a finding

The boundary matters more than the list: without it the agent brings stylistic nitpicks.

- style and formatting, if an automatic tool is responsible for them;
- numbers that live in environment settings — their value is not discussed in a review;
- known and deliberately accepted trade-offs — list them by name, otherwise every pass
  will rediscover them;
- what belongs to the subject of another block: a finding must answer the question of
  **this** block, not any question at all.
