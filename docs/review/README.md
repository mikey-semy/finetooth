# Whole-repository review of finetooth

Placed in the project by the `setup` command as `docs/review/README.md` and adjusted to it. This is the
first file an agent reads: the state of the review lives **on disk, not in the conversation**, so a
session that knows nothing runs one command and sees the full picture.

```sh
python3 skills/finetooth/scripts/review.py status                     # where we are and which block is next
python3 skills/finetooth/scripts/review.py coverage                   # the file → block map; fails if a file is unowned
python3 skills/finetooth/scripts/review.py check                      # the state is consistent
python3 skills/finetooth/scripts/review.py hypotheses H1              # which of the block's hypotheses are closed
python3 skills/finetooth/scripts/review.py roots                      # defect classes: how many instances, what closes each
python3 skills/finetooth/scripts/review.py prompt H1 --role hunter    # a ready prompt for an agent
```

## Layout

| file | what it is |
|---|---|
| `blocks.json` | what the review consists of: the blocks and their files. Edited by hand, rarely |
| `state.json` | how far each block has got. Edited by the tool |
| `invariants.md` | **the project's rules.** Pasted to every agent; they decide what it counts as a defect |
| `blocks/<ID>-<slug>.md` | block manifest: why, what counts as a finding, hypotheses, acceptance criterion |
| `findings.jsonl` | the findings register, one line per finding. Edited by the tool |
| `findings.md` | human-readable summary, **generated** from the jsonl |
| `coverage.tsv` | the coverage map, **generated**; the proof that the review is complete |
| `journal.md` | the decisions journal: what was decided and why. Cannot be recovered — write it right away |
| `prompts/` | optional: your own version of a role template (`hunter.md`, `verify.md`, `fix.md`, `fixreview.md`). No file — the skill's template is used |
| `reports/` | agent reports, named by the tool: `<ID>-<slug>.hunter.md`, `.verify.md`, `.fix.md` (`.fix-N.md` from round 2), `.fixreview-N.md`. The agent writes them itself, not the lead session |

## Working through a block

1. **Manifest.** Write `blocks/<ID>-<slug>.md` — without project-specific hypotheses the
   review comes out "on general grounds". This is the longest part, and it cannot be cut.
2. **Hunter** (`--role hunter`) reads all the block's files and puts forward findings. It writes
   the report and the draft `reports/<ID>-findings.jsonl` itself, to disk. The report must have
   verdicts on all the manifest's hypotheses and a "Coverage limits" section. Then `set-status <ID> hunted`.
3. **Verifier** (`--role verify`) checks every finding against the current code, does its own
   independent pass over the riskiest places and rewrites the block's findings file.
   Rejected ones **are not deleted** — they stay with the rejection reason, otherwise the next
   review finds the same thing. Then `set-status <ID> verified`.
4. **Acceptance.** Read both reports yourself and check them against the acceptance criterion.
   Coverage incomplete — send the block back for another pass, do not close it.
5. **Into the register.** `import <ID>`, then `findings`, then `check`. The plain import
   refuses when the file would erase a finding already recorded against the block or
   overturn a decision already taken — then `import <ID> --append`: what is recorded stays,
   the new rows get the next free numbers.
6. **Journal.** `log <ID> "what was decided and why"`.
7. **Fixing** (`--role fix`) — by a **different** agent, not the one that hunted. A repeat
   round is `--role fix --round N`: without the flag the second fixer's report overwrites
   the first one's. Findings are moved with `set-finding <ID…> fixed --commit <sha>`, and a
   defect class with a third instance is closed by a guard (`--rule <path to the test or
   rule>`), not by a list of fixes.
   **The fix gate:** `set-status <next ID> running` refuses while findings at the `fix_gate`
   severity or above (`high` by default, set in `blocks.json`) are still open in the blocks
   already passed — the method finds faster than a project fixes. `status` shows that debt
   as its own line.
8. **Fix review** (`--role fixreview --diff main...HEAD [--round N] [--scope <half>]`) — a
   fresh agent that did not write the fixes, **before** the change is opened. Its report is
   `reports/<ID>-<slug>.fixreview-<N>.md`, and a block with fixed findings does not pass
   `check` without one. Its confirmed findings go into the register as a top-up
   (`import <ID> --append`), even the ones already fixed. A new round only for a finding of
   medium or higher; low ones are fixed without one.
9. Only after that `set-status <ID> closed`.

⚠️ One agent does not hunt and fix at the same time. ⚠️ A block is not closed without the
acceptance criterion met. ⚠️ Do not run more than two or three agents at once if a build is
running on the same machine — the CPU is fully taken.

## When the code moves under a block already read

`check` keeps a fingerprint of what was read — the block's files, its context and the text
of the hypotheses — and goes red when they change after the review. `restamp <ID>` is not a
way to switch that off: it says on record that the new text was seen. `backfill` fills in
the fingerprints of records written before fingerprints existed.

## Fixing rules

- **The one who found does not fix.** A reviewer who starts fixing stops hunting.
- **And the one who fixed does not verify.** The fixes are the only code the review produces,
  and it is written by the same AI that found the defects.
- **Confirmed — fixed in the same session**, not "write it down and come back". Exception: the
  finding touches a block not yet reviewed.
- Fixes accumulate on one branch and leave as one suggestion per batch; security-critical ones
  — as a separate urgent one, without waiting for the batch.
- In the register the finding gets `status: fixed` and the fix commit:
  `set-finding <ID> fixed --commit <sha>`. A finding that cannot be fixed now is deferred
  with a reason (`deferred --reason "…"`), not left open: a deferral without a reason is
  refused, and the reason is what the summary publishes it by.
- **No references to the review in code**: finding identifiers, block and suggestion numbers must
  not get into comments and tests — they die with this directory.

## What counts as finished

All blocks `closed`, no records with status `open` in `findings.md`, and every rejected
finding has its rejection reason recorded (`check` requires this).

A finding left `deferred` is **not** an unfinished one: it is an accepted risk, and it
leaves the review that way — with the reason, under "Accepted risks" in the summary. What
is forbidden is a deferral nobody signed, which is why the reason is demanded.

## How this directory dies

When the review is finished, **the `docs/review/` directory is deleted whole in one suggestion**, and
what lasts moves to where it really lives: rules into the root instructions file, decisions into
ADRs or the knowledge base, checks into tests and build guards.

This is not a formality. Review documents whose status tables nobody updated describe long-fixed
defects as open and mislead everyone who opens them. The review directory is scaffolding around a
construction site, not part of the building. The industry measures this trouble: findings older
than a year are called "security debt", half of organizations carry it, and in some industries
the average age of an open finding reaches 276 days.

**But one file survives the demolition — the summary.** Without it the next review starts from
zero and rediscovers what was already analyzed and rejected. Auditors do the same: the working
papers go, the report stays, and a repeat audit costs about a tenth of the first one precisely
because there is something to start from.

The summary is written once and never edited again — there are no statuses in it that can go stale:

- **the date and the base commit** — from which revision everything was counted (without it "gone stale" cannot be determined);
- the list of blocks and their acceptance criteria — what exactly counted as checked;
- **the rejected findings with rejection reasons** and the accepted risks: exactly what would
  otherwise be found again;
- what closed each defect class — which guard, test, rule.

With it "the review has gone stale" becomes checkable: `git log <base-commit>..HEAD` over the
block's files shows how much has changed since they were read with human eyes.

## When to do it again

A threshold like "N% of the code changed" does not exist, and that is not our omission: the
certification standards state outright that there is no way to tell from the size of a change
whether its impact is large. A broad change may touch nothing important, a pinpoint one may change everything.

So the reasons are listed as events, not percentages:

- the system boundary or its environment changed;
- a new class of threats or a new way of use appeared;
- **many small changes accumulated** — this is a reason on its own, even if each one was
  insignificant by itself;
- time has passed. A calendar cadence is needed regardless of the content of the changes; the
  benchmark adopted in regulation is twelve months.

A repeat pass creates a **new** block card, not a reopened old one: a returning defect usually
returns by a different path, and merging them is losing history.
