# Whole-repository review of {{PROJECT}}

Placed in the project by the `setup` command as `docs/review/README.md` and adjusted to it. This is the
first file an agent reads: the state of the review lives **on disk, not in the conversation**, so a
session that knows nothing runs one command and sees the full picture.

```sh
{{CLI}} status                     # where we are and which block is next
{{CLI}} coverage                   # the file → block map; fails if a file is unowned
{{CLI}} check                      # the state is consistent
{{CLI}} hypotheses H1              # which of the block's hypotheses are closed
{{CLI}} prompt H1 --role hunter    # a ready prompt for an agent
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
| `prompts/` | optional: your own version of a role template (`hunter.md`, `verify.md`, `fix.md`). No file — the skill's template is used |
| `reports/` | agent reports. The agent writes them itself, not the lead session |

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
5. **Into the register.** `import <ID>`, then `findings`, then `check`.
6. **Journal.** `log <ID> "what was decided and why"`.
7. **Fixing** (`--role fix`) — by a **different** agent, not the one that hunted.
8. **Diff review** — by those who did not write it, **before** the suggestion is opened. Only after
   that `set-status <ID> closed`.

⚠️ One agent does not hunt and fix at the same time. ⚠️ A block is not closed without the
acceptance criterion met. ⚠️ Do not run more than two or three agents at once if a build is
running on the same machine — the CPU is fully taken.

## Fixing rules

- **The one who found does not fix.** A reviewer who starts fixing stops hunting.
- **And the one who fixed does not verify.** The fixes are the only code the review produces,
  and it is written by the same AI that found the defects.
- **Confirmed — fixed in the same session**, not "write it down and come back". Exception: the
  finding touches a block not yet reviewed.
- Fixes accumulate on one branch and leave as one suggestion per batch; security-critical ones
  — as a separate urgent one, without waiting for the batch.
- In the register the finding gets `status: fixed` and the fix commit:
  `set-finding <ID> fixed --commit <sha>`.
- **No references to the review in code**: finding identifiers, block and suggestion numbers must
  not get into comments and tests — they die with this directory.

## What counts as finished

All blocks `closed`, no records with status `open` in `findings.md`, and every rejected finding
has its rejection reason recorded (`check` requires this).

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
