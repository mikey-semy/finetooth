---
name: finetooth
description: Whole-repository review in blocks — with a file → block coverage map, hypotheses as the second denominator, four agent roles (hunter, verifier, fixer, fix reviewer) and on-disk state that survives session changes. Use when asked for a full or whole-codebase review or audit that must cover every file rather than a diff, to resume a review already in progress (the repository has docs/review/), or to run the hunter, verify, fix or fixreview role on a review block.
license: MIT for the additions; the base was handed over by its author without a license — full terms in LICENSE
compatibility: Requires git and Python 3 (standard library only; tested on 3.12 and 3.14). Run from the directory of the repository under review.
metadata:
  version: "0.7.0"
  original-author: "Georgiy Khudobandaev (https://github.com/Georgiy-Khudobandaev)"
  source: "https://github.com/mikey-semy/finetooth"
---

# Whole-repository review

A review of all the code, not of a diff: the repository is cut into blocks, every block goes
through three roles, and completeness is proven by the coverage map — not one file without a
block. Sessions change, context runs out, so **all state lives on disk** in the project's
`docs/review/` and is read back by the tool. Keep nothing in the memory of the conversation.

## The tool

Everything goes through `scripts/review.py` from this skill, **run from the root of the
repository under review** (the root is taken from git by the working directory):

```sh
python3 <path-to-skill>/scripts/review.py status
```

Below it is called `review`. If `docs/review/blocks.json` has a `cli` field, the project calls
the tool its own way (`npm run review --`, `make review`) — use that. Every refusal from the
tool names the command that fixes it: read the refusal, do not guess.

## Getting started

**The repository already has `docs/review/`** — a review is in progress. Do not start a parallel
one of your own:

1. `review status` — where we are and which block is next; `review next` — its id.
2. `review check` — is the state consistent. Red gets fixed first.
3. `docs/review/journal.md` — what was decided before you and why.

**There is no directory** — a review is being set up:

1. `review setup --project <Name>` (plus `--cli "<command>"` if the project calls the tool its
   own way, and `--lang ru` for Russian) — skeleton `blocks.json`, `invariants.md`, the entry
   point `docs/review/README.md`. The `lang` field in `blocks.json` (`en` by default, `ru`)
   selects the language of the prompt templates and assets; the Russian ones sit next to the
   English with a `.ru.md` suffix.
2. `docs/review/invariants.md` — the rules of THIS project. It is pasted to every agent and
   decides what the agent will count as a defect. Generic words are useless — write what the
   project has already paid for.
3. `docs/review/blocks.json` — `gates` (the commands of the project's gates) and the blocks:
   cross-cutting first, domain next, live-system last. `review inventory` prints the
   repository tree with sizes and ownership — cut by it. A block is what can be read in one
   sitting (the `readable_lines` ceiling, 6000 lines by default; `review sizes` shows who is
   above it). A block that reading cannot prove (test quality, performance, scanners) gets
   `"proof": "measured"`: the proof is the artifacts from the manifest, and the ceiling does
   not apply. A block without `paths` is a live system. Sample —
   [assets/blocks.example.json](assets/blocks.example.json).
4. `review init`, then `review coverage` — work through the unowned files until there are
   zero. **A human assigns a file to a block**: a file caught by a pattern match will be
   counted as read without having been read.

## Working through a block

1. **Manifest** `docs/review/blocks/<ID>-<slug>.md`: why the block exists, what counts as a
   finding, 10–15 numbered hypotheses about this project, an acceptance criterion that cannot
   be met without reading the code. Sample — [assets/manifest.example.md](assets/manifest.example.md).
   Without project-specific hypotheses the review comes out "on general grounds"; do not cut this part.
2. **Hunter.** `review prompt <ID> --role hunter` prints a ready prompt — hand it to a subagent
   **whole and unedited**. The agent writes the report and the draft findings to disk itself.
   Then `review set-status <ID> hunted`.
3. **Verifier** — a different agent: `review prompt <ID> --role verify`. Checks every finding
   by execution, does its own pass over the most dangerous places, rewrites the findings file.
   Rejected findings are not deleted — they stay with the reason. Then `review set-status <ID> verified`.
4. **Acceptance.** Read both reports yourself and check them against the acceptance criterion.
   Coverage incomplete — the block goes back for another pass, not to closure.
5. **Register.** `review import <ID>`, `review findings`, `review check`.
6. **Journal.** `review log <ID> "what was decided and why"` — right away: this cannot be recovered.
7. **Fixing** — yet another agent: `review prompt <ID> --role fix`. Cut assignments by related
   areas, not one finding at a time. Run the gates and the revert check yourself after the
   fixer. Findings are moved with `review set-finding <ID…> fixed --commit <sha>` (several ids
   at once); a defect class with a third instance is closed by a guard
   (`--rule <path to the test or rule>`), not by a list of fixes. Deferring is allowed only
   with a reason (`deferred --reason`).
8. **Fix reviewer** — a fresh agent that did not write the fixes:
   `review prompt <ID> --role fixreview --diff main...HEAD [--round N] [--scope <half>]`.
   The diff is pasted into the prompt whole; two agents on two halves of the diff is fine. Its
   confirmed findings go into the register as a top-up import (`import <ID> --append`), even
   the ones already fixed. Rounds repeat while the reviewer answers "another round is needed";
   a round that finds a defect introduced by the previous round is a signal to stop and think.
9. Only after that `review set-status <ID> closed`: without a fix reviewer's report a block
   with fixes cannot be closed.

## Rules not to break

- One agent does not hunt and fix at the same time; the one who found does not fix; the one
  who fixed does not verify. A repeat fix goes to a fresh agent, not the same one: the
  assignment is self-contained, and the first attempt's mistakes are mistakes of attention.
- A block boundary is a full stop: report to the owner and wait for the go-ahead on the next
  one. An open question is repeated in full, each with who decides and a recommendation.
- A block is not closed without the acceptance criterion met and without the verifier's report.
- Checking outside your own repository — against a fresh `origin` after `git fetch`: a stale
  tree shows what is fixed as broken.
- No references to the review in code: finding and block numbers die with `docs/review/`.
- Do not run more than two or three agents at once if a build is running on the machine.

## What `review check` holds

A red check means the work is not done, even if it looks done. Among other things it catches:
a file without a block and a stale coverage map; a file of a readable block not named by full
path in any report (what was read — as a list, what was not — in the coverage limits); a
hypothesis without a verdict or with conflicting verdicts; a hunter report without a
"Coverage limits" section and an empty verifier report; a deferred finding without a reason;
a block in `blocked` without a note; phases out of order; a block closed with fixes but
without a fix review; a block and a finding closed on a different version of the code
(fingerprints — `review restamp` if the changes are unrelated, `review backfill` for records
older than the fingerprints); a finding without a rejection reason, a fix commit that does not
touch the file, a duplicate of a nonexistent finding, a guard at a nonexistent path; a tree
more than a week behind the server.

## When the review is finished

All blocks `closed`, no open findings, every rejected one has a reason. Then the
`docs/review/` directory **is deleted whole in one change**, and what lasts moves out: rules
into the root instructions file, decisions into ADRs, checks into tests. One file remains —
the summary: the date and the base commit, the blocks and their criteria, the rejected
findings with reasons, what closed each defect class. Without it the next review starts from zero.

## Files of the skill

- [references/hunter.md](references/hunter.md), [references/verify.md](references/verify.md),
  [references/fix.md](references/fix.md), [references/fixreview.md](references/fixreview.md)
  — the role templates. `review prompt` assembles the prompt from them; read them only to
  understand or adjust a role. A project may keep its own version in
  `docs/review/prompts/<role>.md` — then that one is used. The Russian versions sit next to
  them as `<role>.ru.md`.
- [references/lessons.md](references/lessons.md) — the lessons of two reviews the rules grew
  out of: read before the first block.
- [assets/](assets/) — samples: blocks, manifest, invariants, journal, banner for the root
  instructions file, `make` and `package.json` targets, a guard example.
