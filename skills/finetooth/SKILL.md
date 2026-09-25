---
name: finetooth
description: Whole-repository review in blocks — with a file → block coverage map, hypotheses as the second denominator, four agent roles (hunter, verifier, fixer, fix reviewer) and on-disk state that survives session changes. Use when asked for a full or whole-codebase review or audit that must cover every file rather than a diff, to resume a review already in progress (the repository has docs/review/), or to run the hunter, verify, fix or fixreview role on a review block.
license: MIT
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
python3 <path-to-skill>/scripts/review.py version   # which version of the kit this project is on
```

Below it is called `review`. If `docs/review/blocks.json` has a `cli` field, the project calls
the tool its own way — use that. Every hint and every refusal is assembled from it
(`<cli> coverage`, `<cli> restamp H1`), so the value has to be a command that takes the
subcommand and its flags after it: `npm run review --`, a shell wrapper of the project's
own. `make` is not one of them — it reads `--role` as its own option — so a project on
`make` leaves `cli` unset and gets hints with the real path to the tool
([assets/makefile-snippet.mk](assets/makefile-snippet.mk) has the targets for the everyday
commands). Every refusal from the tool names the command that fixes it: read the refusal,
do not guess.

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
   not apply. A criterion that enumerates across the program ("every place that changes
   data") is a sweep, not reading: declare it in `sweep`, and the hunter enumerates by a
   script at `docs/review/sweeps/<ID>.<ext>`, then reads the hits. A block without `paths` is a live system. Sample —
   [assets/blocks.example.json](assets/blocks.example.json).
4. `review init`, then `review coverage` — work through the unowned files until there are
   zero. **A human assigns a file to a block**: a file caught by a pattern match will be
   counted as read without having been read.
5. `review coupling` — files that change together (from `git log`) but sit in different
   blocks: the seams nobody reads. For each pair it names the `ref_paths` entry and the
   hypothesis to add to the manifest; several pairs between the same two blocks are a seam
   block waiting to be cut. Shared nodes (a schema, a dictionary) are listed apart.
6. `review order` — the blocks in the order worth walking them: the cost of failure first
   (`risk` on the block: `critical|high|medium|low`; without it the declared order speaks),
   change frequency from `git log` second. A report, not a rewrite: reorder `blocks.json`
   yourself if you agree.

## Working through a block

1. **Manifest** `docs/review/blocks/<ID>-<slug>.md`: why the block exists, what counts as a
   finding, 10–15 numbered hypotheses about this project, an acceptance criterion that cannot
   be met without reading the code. Sample — [assets/manifest.example.md](assets/manifest.example.md).
   Without project-specific hypotheses the review comes out "on general grounds"; do not cut this part.
2. **Hunter.** `review prompt <ID> --role hunter` prints a ready prompt — hand it to a subagent
   **whole and unedited**. The agent writes the report and the draft findings to disk itself.
   Then `review set-status <ID> hunted`. Headless, with the spend measured and written to the
   journal: `assets/run-role.sh <ID> hunter` (the same for `verify`, `fix`, `fixreview`;
   the turn cap is twice what the first measured run of the role needed).
3. **Verifier** — a different agent: `review prompt <ID> --role verify`. Checks every finding
   by execution, does its own pass over the most dangerous places, rewrites the findings file.
   Rejected findings are not deleted — they stay with the reason. Then `review set-status <ID> verified`.
4. **Acceptance.** Read both reports yourself and check them against the acceptance criterion.
   `review hypotheses <ID>` shows which of the block's hypotheses got a verdict and where.
   Coverage incomplete — the block goes back for another pass, not to closure.
5. **Register.** `review import <ID>`, `review findings`, `review check`. The plain import
   refuses when the file would erase a finding already recorded against the block or overturn
   a recorded decision — then `import <ID> --append` (or `--force`, deliberately).
6. **Journal.** `review log <ID> "what was decided and why"` — right away: this cannot be recovered.
7. **Fixing** — yet another agent: `review prompt <ID> --role fix [--round N]`. Cut assignments
   by related areas, not one finding at a time. A repeat round needs `--round N`: without it
   the second fixer writes over the first one's report, and the fix reviewer of round N is
   pointed at `<ID>-<slug>.fix-N.md`, which nothing would have written. Run the gates and the
   revert check yourself after the fixer. Findings are moved with
   `review set-finding <ID…> fixed --commit <sha>` (several ids at once); a defect class with
   a third instance is closed by a guard (`--rule <path to the test or rule>`), not by a list
   of fixes. The guard is recorded only on the findings named in the command — name the
   instances it goes red on; `review roots` lists the classes, their instances and which
   guard each instance carries, and flags a root whose instances disagree.
   Deferring is allowed only with a reason (`deferred --reason`), and a deferred finding
   leaves the review as an accepted risk, published in the summary with that reason.
   **The fix gate:** `review set-status <next ID> running`
   refuses while findings at `fix_gate` severity or above (`high` by default, set in
   `blocks.json`; `"none"` switches it off) are open in the blocks already passed — the
   method finds faster than a project fixes, and a finding that never reaches a fix is debt.
   `review status` shows this debt as its own line.
8. **Fix reviewer** — a fresh agent that did not write the fixes:
   `review prompt <ID> --role fixreview --diff main...HEAD [--round N] [--scope <half>]`.
   The diff is pasted into the prompt whole, and `--scope` names a reviewer's half in its
   report without shrinking it: a diff too large for one agent is split by giving each a
   narrower `--diff` range. Its
   confirmed findings go into the register as a top-up import, even the ones already fixed,
   with the command its prompt names: `import <ID> --append --round N --diff <base>..<tip>`
   records which review found them (`found_in`). A new round only for a finding of medium or
   higher; low ones are fixed by the fixer or by the lead, and a lead's fix is marked in the
   journal and the PR as having no independent review. **The loop signal:** when the top
   finding of review N−1 (medium or higher) lies on a line fix round N−1 wrote, by the lines of
   its diff, `prompt --role fix --round N` refuses and `check` warns — another round would fix
   its own last fix. The next move is a human's: a different mechanism, a revert of the class
   to its last strict state, or closing the block. Record it with
   `review decide <ID> "<decision>"` (it goes to the journal and into the next fix and fix
   review prompts, and lifts the refusal); a decision to close is carried out with `set-status`.
   Give each round its own `--diff` range and the signal means "this round".
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
  `review refs` lists the ones that got in; `check` warns about them.
- Do not run more than two or three agents at once if a build is running on the machine.

## What `review check` holds

A red check means the work is not done, even if it looks done. Among other things it catches:
a file without a block and a stale coverage map; a file of a readable block not named by full
path in any report (what was read — as a list, what was not — in the coverage limits); a
hypothesis without a verdict or with conflicting verdicts; a hunter report without a
"Coverage limits" section and an empty verifier report; a deferred finding without a reason;
an open finding older than a week (a warning);
a block in `blocked` without a note; phases out of order; a block closed with fixes but
without a fix review; a block and a finding closed on a different version of the code
(fingerprints — `review restamp` if the changes are unrelated, `review backfill` for records
older than the fingerprints); a finding without a rejection reason, a fix commit that does not
touch the file, a duplicate of a nonexistent finding, a guard at a nonexistent path; a tree
more than a week behind the server; the loop signal without a recorded decision (a warning).

## In CI and on the platform

`review check` is the gate a project runs in CI and makes required: a merge that edits code
under an open finding, or leaves the register contradicting the tree, stays red.
`review sarif` prints the open and deferred findings as SARIF 2.1.0 (`--out <file>` writes
it instead) for GitHub code scanning — the findings show in the Security tab and on the
lines of a pull request; a deferred one is marked as an accepted risk. Ready jobs:
[assets/github-actions-snippet.yml](assets/github-actions-snippet.yml) (`check` plus the
SARIF upload) and [assets/gitlab-ci-snippet.yml](assets/gitlab-ci-snippet.yml) (`check`;
it says what GitLab shows and on which tier).

## When the review is finished

All blocks `closed`, no open findings, every rejected one has a reason and every deferred
one — a deferral is an accepted risk that leaves the review with its reason, not an
unfinished fix. Then
`review summary` writes the one file that outlives the directory (`docs/review-summary.md`
by default): the date and the base commit, the blocks and their acceptance criteria, the
rejected findings with reasons, the accepted risks, what closed each defect class. Only then
the `docs/review/` directory **is deleted whole in one change**, and what lasts moves out:
rules into the root instructions file, decisions into ADRs, checks into tests. Later,
`review summary --aged docs/review-summary.md` says how far each block has drifted since the
base commit — the only thing a re-run needs to start from. Without the summary the next
review starts from zero.

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
  instructions file, `make` and `package.json` targets, CI jobs for GitHub Actions and
  GitLab, a guard example;
  [assets/run-role.sh](assets/run-role.sh) — a role run through `claude -p` with the event
  stream kept and the spend logged.
- [scripts/axes.py](scripts/axes.py) — the spend of one run by axis (cache, turns, tool
  output, re-reads) from that stream; `--journal` gives the one line `run-role.sh` writes,
  `--reply` the agent's answer. It is the only reader of the stream: a killed run leaves
  its last line half-written, and a second parser dies on it.
