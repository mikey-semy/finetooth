# T4 — fix review, round 2

Range `d33527c..HEAD`, seven commits, 261 KB / 1759 lines of diff — **read in full**, no
`--scope` split needed.

## What was checked and how

**Read in full**, and re-read from the files on disk rather than from the pasted diff: the diff
is the claim about what changed, `git show` is what changed. The register diff was taken field
by field with a script instead of by eye, which is how the largest finding below surfaced — it
sits in hunks the pasted diff shows and the report never mentions.

**Proven by reverting.** Everything went through the round's own substitution mechanisms
(`FINETOOTH_SHELL_GATE`, `FINETOOTH_TOOL`) so that nothing was written into the tree; the one
mutation that had to touch a real file (`README.md`, for R2-001c) was restored byte for byte
and `git status --porcelain` verified empty afterwards.

| what was reverted | result |
|---|---|
| `.github/dco.sh` back to `d33527c` | `bash -n` rc 0 — the reverted script parses, so the red is the tests' — `DcoGateTest` 3 of 9 red: `test_подпись_с_адреса_с_метасимволами_проходит`, `test_подпись_на_похожий_адрес_не_засчитывается`, `test_нерешаемый_диапазон_роняет_ворота_и_называет_починку`. The other six green on both scripts. |
| `scenario_count()` back on `unittest.defaultTestLoader` | `test_замер_числа_сценариев_не_зависит_от_способа_запуска` red (`0 != 341`); green with the fix |
| the suite at `d33527c` fed to `CommandSweepRuleTest`'s rule | names exactly `test_ни_одна_команда_не_пишет_вне_каталога_ревью`; `[]` on the suite at HEAD |
| `guard-grep.sh`: the marker no longer SPENT (T1-022's defect) | `GuardGrepTest` red — `ShellGateMutationTest` **green** → R2-001b |
| `review.py`: `cmd_backfill`'s idempotence early-return deleted (T3-004's defect) | `IdempotenceTest` red — `ShellGateMutationTest` **green** → R2-001a |
| `README.md`: the coupling thresholds back to "six or more blocks" and the bare 95th percentile (T4-005's defect) | `test_пороги_из_документов_читаются_из_кода` red — `test_число_сценариев_в_документах_равно_настоящему`, which the register now names for T4-005/T4-006, **green** → R2-001c |
| the suite at `d33527c` fed to `SourceRuleTest._rules_without_samples` | `([], [])` — the guard the register now names for T4-021 is green on T4-021's own defect → R2-001d |
| `review.py`: the `no manifest` gate of `cmd_check` deleted (T1-007's shape) | `GateRegistryTest` red — `ShellGateMutationTest`, which the round wrote in its place, **green** → R2-001e |

**Gates checked by violation, not by reading.** The new CI-step guard was fed the repository's
real workflow with, one at a time: the `Run the tests` step deleted, the whole `unittest` job
deleted — red on both, where the round-1 two-anchor logic returns `[]` for both (reproduced).
Three further shapes were pushed through it; two of them pass and should not (R2-003).

**Measured, not read:** the scenario count (341 by a fresh loader and by `defaultTestLoader`
alike; 341 in README.md, README.ru.md and AGENTS.md — the round's central number holds); the
count at the range's base (325, so the range adds 16 tests, not the 23 the report claims —
R2-008); en↔ru parity of the new CHANGELOG section (6 bullets each, the same 14 test/class
names, the same numbers, every named test present in the suite); the tracked-document list the
new markdown rule walks (12 root documents), and the same rule applied to all 78 tracked `.md`
files to look for a second address of the glued-paragraph defect — there is none.

**Reproduced live:** `.github/dco.sh` was run end to end against throwaway repositories for
the `+`-address, look-alike-address, unresolvable-range and empty-range cases, and once more
with a 200 KB commit message to test whether `set -o pipefail` over `signoff_addresses | grep
-q` could refuse an honest sign-off — it does not (see "Checked and found correct").
`review roots`, `review check` and `review findings` were run on the register as committed.

**Not done:** `skills-ref validate` was not re-run — the round changes nothing under
`skills/finetooth/` (`git diff d33527c..HEAD -- skills/` is empty, verified). The full suite
was run once, at the end; its result is at the bottom of this report. `GateMutationTest` could
not be used as a control in the `FINETOOTH_TOOL` measurements: it skips itself when that
variable is set, so the T1-007 case below rests on reading the code, not on a run.

## Findings

### R2-001 · medium · Ten findings were given a guard that does not fire on them — T4-020 reopened wider, inside its own fix

**Location:** `docs/review/findings.jsonl` (the `rule` field of T1-007, T1-011, T1-022,
T3-003, T3-004, T3-007, T3-015, T4-005, T4-006, T4-021), commits `5bf74c5` and `e4aba43`

**What is wrong:** T4-020 said the register recorded a class as closed by a guard that does not
close it. The fix wrote or rewrote the `rule` field on sixteen pre-existing findings — thirteen
of them in blocks T1, T2 and T3, which were not this round's assignment — so that `review
roots` prints one guard per root. Of those sixteen, **ten name a guard that is green on the
finding's own defect.** The fixer's report states the opposite ("Each finding's `rule` is now
the guard that fires on that finding"), its table lists only seven of the sixteen rows, and for
two of those seven the table contradicts what was actually committed.

**Failure scenario:** four measured cases, each the defect restored and both candidate guards
run:

| finding | rule the round recorded | on the finding's own defect restored |
|---|---|---|
| a. T3-004 (`cmd_backfill` loses its idempotence early-return) | `ShellGateMutationTest` | **green** (`Ran … OK`); `IdempotenceTest` red |
| b. T1-022 (`guard-grep.sh`: a marker no longer SPENT) | `ShellGateMutationTest` | **green**; `GuardGrepTest` red |
| c. T4-005 / T4-006 (README back to "six or more blocks" and the bare 95th percentile) | `test_число_сценариев_в_документах_равно_настоящему` | **green**; `test_пороги_из_документов_читаются_из_кода` red |
| d. T4-021 (the suite as it stood, the two-anchor CI guard in it) | `SourceRuleTest` | **green** (`_rules_without_samples` → `([], [])` on the pre-fix suite) |
| e. T1-007 (a `cmd_check` gate deleted — the finding's own shape) | `ShellGateMutationTest` | **green**; `GateRegistryTest`, the value this round **overwrote**, red |

Case (e) is the sharpest: the round replaced a guard that goes red on the finding with one that
does not. Two more are green by construction rather than by measurement:
`ShellGateMutationTest` reads only `.github/dco.sh` and
`skills/finetooth/assets/guard-grep.sh` and never invokes `review.py` at all, so it cannot fire
on T1-011 (`stale_tree`) or on
T3-007 (mechanisms outside `cmd_check`); `CommandSweepRuleTest` reports only test functions
that take the command list from the tool and run commands from a variable, so it cannot fire on
T3-003 (a `GATES` entry re-pointed to an unrelated test — whose correct guard,
`GateMutationTest`, the round **overwrote**) or T3-015 (the tool spawned as PATH `python3`,
held by `TestSuiteRuleTest`).

The consequence is the one T4-020 named. `review roots` now prints:

```
7 × a gate that cannot go red  — guard: tests/test_review.py::ShellGateMutationTest
      T1-007  T1-008  T1-011  T1-022  T3-004  T3-007  T4-026
4 × a number in a public document not checked against its source
      — guard: …::test_число_сценариев_в_документах_равно_настоящему
      T4-004  T4-005  T4-006  T4-024
```

Of the seven instances of the largest root, two are actually held by the named guard (T1-008,
T4-026). Restore T3-004's defect and the register, `roots` and the summary all say the class is
closed by a guard that is green. Before this round that root's printed guard
(`GateRegistryTest`) went red on T1-007's own shape — measured, case (e); after it, the printed
guard does not.

**Measured four times, plus once against the whole set:** `_rules_without_samples` and
`_sweeps_without_body_check` were also fed the suite at `d33527c` to confirm the two new class
rules behave as claimed — `CommandSweepRuleTest` does (it names exactly the defective sweep),
`SourceRuleTest` does not (case d).

**Why it is a defect:** invariant 2 — a guard that can be holed with the suite green is not a
guard; the review's own rule that a class with three instances is closed by a guard, not by a
list. And rule 1 of the fix review: the report's table says T4-005/T4-006 got
`test_пороги_из_документов_читаются_из_кода`; the register committed in the same commit says
the scenario-count test. Rule 6 as well: thirteen of the sixteen rows are outside T4's list of
findings and are named nowhere in the report as incidental.

**Introduced by this round.** Six of the ten wrong values *replaced* an existing value, and in
three cases (T1-007, T3-003, T3-015) the replaced value was the correct one.

**Confidence:** confirmed — five measured (a–e), five by construction from what the named
guards read.

**Root:** a class recorded as closed by a guard that does not close it

### R2-002 · medium · The write-boundary sweep reaches `set-finding`'s body and still never reaches its write, so T4-023's own scenario stays open for one of the three commands it named

**Location:** `tests/test_review.py:3386` (`WriteBoundaryTest.test_ни_одна_команда_не_пишет_вне_каталога_ревью`), `BODY_ARGV` at `tests/test_review.py:3306`

**What is wrong:** T4-023 was that `set-status`, `set-finding` and `log` never got past
argparse and were therefore outside the write-boundary guard. The fix gives each command
arguments at which it "reaches its body" and asserts that argparse did not refuse. For
`set-finding` the argument chosen is an id that does not exist on the stand, so the command
refuses before writing anything at all.

**Failure scenario:** run on the sweep's own stand (the `WriteBoundaryTest` setUp, verbatim):

```
set-status   rc=0  argparse_refused=''  stderr=''
set-finding  rc=2  argparse_refused=''  stderr='error: finding H1-001 is not in the register'
log          rc=0  argparse_refused=''  stderr=''
```

`set-finding`'s register write is never executed, so T4-023's stated scenario — "a future
change that makes `log` or `set-finding` write outside `docs/review/` (register redirected, an
`--out` flag) passes the guard" — remains true for `set-finding`: point its register write at
the repository root and the sweep is still green, because the command exits at the id check
first. `argparse_refused()` does not notice, by design: it only looks for argparse's three
complaints, and this is the command's own refusal.

**Why it is a defect:** invariant 2, and SECURITY.md's boundary promise, which the report
presents as now held by a run for all the writing commands ("The same sweep now runs them for
real … and requires the tree outside `docs/review/` to be untouched"). Two of the three run for
real; the third does not. The remedy is one line — an id the stand actually has, or an `import`
in `setUp`.

**Introduced by this round** (the argument table is new in `aacc9b7`); the underlying gap is
the one T4-023 named and is only two thirds closed.

**Confidence:** confirmed

**Root:** guard enumerates its subject without exercising it

### R2-003 · low · The new CI guard counts a step that neutralises the gate it runs

**Location:** `tests/test_review.py:5496` (`_runs_command`)

**What is wrong:** the rule requires the same program by name and every documented argument
present and in order, and deliberately allows a wider step. A step that adds `|| true`, or
narrows the run with `-k`, is wider in exactly that sense and counts as running the gate.

**Failure scenario:** measured against the repository's real workflow with one step rewritten:

```
run: python3 -m unittest discover -s tests -k НетТакогоТеста        → guard GREEN (0 tests run)
run: python3 -m unittest discover -s tests -k НетТакого || true     → guard GREEN (CI can never go red)
run: .github/dco.sh HEAD~1..HEAD                                     → guard GREEN (one commit checked)
```

Branch protection keeps requiring a green `tests` workflow, CONTRIBUTING keeps telling a
contributor the suite is the gate, and the guard that exists to tie the two keeps passing. This
is the same shape as T4-021, narrowed but not closed: deletion is now caught, neutralisation is
not.

**Why it is a defect:** invariant 1 — the gate must not be satisfiable without the state it
asserts. A shell operator that discards the exit code (`|| true`, `|| :`, `; true`) and a
selector that empties the run are the two cheapest ways to silence a CI step while leaving it
in the file.

**Introduced by this round.** **Confidence:** confirmed

**Root:** class guard keyed on incidental syntax

### R2-004 · low · The glued-paragraph rule does not see a numbered list item

**Location:** `tests/test_review.py:5545` (`_glued_to_list_item`)

**What is wrong:** the rule recognises the preceding line as a list item only through
`^\s*[-*+] `. An ordered item (`1. `, `1) `) is a list item with the same lazy-continuation
behaviour, and the rule's own exclusion list already knows the shape (`\d+[.)] ` is excluded
from being a paragraph) — it is simply not accepted as an opener. A continuation indented by a
single space is missed for the same reason.

**Failure scenario:** measured on the rule itself:

```
"- item\nParagraph.\n"    → ['2: Paragraph.']   (caught)
"1. item\nParagraph.\n"   → []                  (missed)
"1) item\nParagraph.\n"   → []                  (missed)
"- item\n Paragraph.\n"   → []                  (missed; renders as continuation)
```

RELEASING.md, CONTRIBUTING.md and `docs/review/README.md` all carry numbered procedures; a
paragraph written flush under step 4 becomes part of step 4 in the rendered release notes and
the rule described in the CHANGELOG as "a paragraph may not start on the line after a list
item" stays green. No live occurrence today: the same rule run over all 78 tracked `.md` files
reports nothing, so this is a gap in the guard, not an open defect in the documents.

**Why it is a defect:** the class was closed by a rule rather than by two fixed places, and the
rule covers less than the sentence that describes it — the pattern T4-020 and T4-021 are both
instances of.

**Introduced by this round.** **Confidence:** confirmed

**Root:** class guard keyed on incidental syntax

### R2-005 · low · CHANGELOG (both languages) says six findings for a round that closed eight

**Location:** `CHANGELOG.md:102`, `CHANGELOG.ru.md:102`

**What is wrong:** "The fix review of block T4, six more findings, all closed here" — the
register records eight closed in this round (T4-019…T4-026), and the fix report opens with
"Eight findings handed over, **8 closed**". T4-020 (the register's wrong guards) and T4-025
(the round-1 report naming a guard that does not exist) appear in no public entry in either
language.

**Failure scenario:** release notes are taken from this section verbatim (RELEASING gate 4). A
reader reconciling the release against the review's own numbers — the thing the kit asks of its
users — finds six against eight with nothing saying which is right. The neighbouring block
paragraphs set the convention that the number is the register's ("Block T2 … 15 findings, all
closed here", and T2 has 15).

**Why it is a defect:** the block's own definition of a finding — "a number that disagrees with
its source (a measured cost, a test count, **a finding count**)" — and the precedent the block
exists for (an Unreleased entry that carried wrong totals, T1/R5-002).

**Introduced by this round.** **Confidence:** confirmed

**Root:** a number in a public document not checked against its source

### R2-006 · low · The fix report states twenty-three new tests; the range adds sixteen

**Location:** `docs/review/reports/T4-repo-contract.fix-2.md` ("Twenty-three of those 341 are
this round's"; "this round's twenty-three new tests")

**What is wrong:** measured, the suite goes from 325 at `d33527c` to 341 at HEAD — 16 new
scenarios. The diff adds 18 `def test_` methods and removes 2 (one renamed, one moved), which
is the same 16. Twenty-three matches nothing in the range.

**Failure scenario:** the identical class of error the round itself closed one document over:
T4-025 was raised because the round-1 report "quotes 270 tests against the range's 296", and
this round's own report corrects it with a note — while stating a number of its own that the
range does not support. The next reader checking round 2 against its report hits the same
ambiguity T4-025 describes: was a test dropped, renamed, or never written?

**Why it is a defect:** fix-review rule 1 (a discrepancy between report and diff is a finding)
and AGENTS.md rule 4 (numbers are derived from measurement). It is also the round's own claim
about its work: the report leans on "twenty-three new tests" when arguing that the runtime
figures still hold.

**Introduced by this round.** **Confidence:** confirmed

**Root:** a number in a public document not checked against its source

### R2-007 · low · The defect fixed as T4-022 is still recorded open as T2-020, and `check` is red on it

**Location:** `docs/review/findings.jsonl` (T2-020), `CHANGELOG.md:76`

**What is wrong:** T4-022 and T2-020 are the same defect found by two round-1 fix reviewers —
the T2 paragraph glued to the last T4 bullet in both CHANGELOGs. This round fixed the text and
closed T4-022, and left T2-020 `open`. The fixer's report does not mention it, in the findings
table or under "found, not fixed".

**Failure scenario:** `review check` now reports `finding T2-020: code in CHANGELOG.md changed
since import` and the register carries an open low finding for a defect that no longer exists.
The lead resolving the block has to rediscover that the two records are one defect; `review
findings` shows 7 open where 6 are real; and a duplicate that is neither `dup_of` nor `fixed`
is the state the register's duplicate rules exist to prevent.

**Why it is a defect:** rule 5 of the fix review — the fix goes to every address of the defect,
and the register is an address. The round demonstrably knew about the twin: the CHANGELOG entry
it wrote for T4-022 describes the T2 paragraph.

**Introduced by this round** (the text fix is what made T2-020 false).

**Confidence:** confirmed

**Root:** the same defect recorded twice and closed once

### R2-008 · low · The shell-gate mutation rule takes its list of gates from a hand-written dict, not from the tree

**Location:** `tests/test_review.py:5102` (`ShellGateMutationTest.GATES`)

**What is wrong:** the refusal is found by shape, but the *scripts* are a two-entry literal.
Three shell scripts are tracked (`.github/dco.sh`, `skills/finetooth/assets/guard-grep.sh`,
`skills/finetooth/assets/run-role.sh`); nothing reads the list from `git ls-files`, and nothing
fails when a script is outside it. Every neighbouring rule this round wrote takes its subject
from git (the documents, the commands, the workflow steps).

**Failure scenario:** a fourth gate script is added — the kind of thing this repository keeps
adding, `dco.sh` itself being three days old — with two refusals and no tests. The suite is
green, `roots` still prints `ShellGateMutationTest` as the guard of "a gate that cannot go
red", and the CHANGELOG still says "a refusal written tomorrow falls under the rule by itself",
which is true only inside a listed script. No live instance today: `run-role.sh`'s two
literal-digit refusals (`exit 2` for an unknown role, `exit 3` for a lost journal write) are
both held by tests that assert the exit code, so the omission costs nothing yet.

**Why it is a defect:** the class is declared closed by a rule; the rule's subject list is a
list of places, which is what the rule was written to replace.

**Introduced by this round.** **Confidence:** confirmed

**Root:** class guard keyed on incidental syntax

### R2-009 · low · The sweep rule is satisfied by naming `argparse_refused`, and blind to a sweep that passes the command as a star-arg

**Location:** `tests/test_review.py:5268` (`_sweeps_without_body_check`)

**What is wrong:** the rule flags a sweep unless the text of the function matches
`argparse_refused` anywhere. `ast.unparse` keeps docstrings and dead code, so a mention
satisfies it; and the sweep is recognised only when the first argument of `.run(...)` is a bare
`Name`.

**Failure scenario:** measured on invented sweeps, all three of which the rule passes:

```
a sweep whose docstring says "we do not call argparse_refused here"   → []  (not flagged)
a sweep with a dead `argparse_refused = None`                         → []  (not flagged)
a sweep calling self.s.run(*[cmd])                                    → []  (not seen at all)
```

The next sweep written by copying a neighbour and then simplified — the exact history of
T3-002, T3-012 and T3-014 — is outside a rule the report describes as covering "the sweep
nobody has written yet".

**Why it is a defect:** invariant 1 as it applies to the guard: it must not be satisfiable
without the state it asserts. The honest form of the check is to require the call, not the
token.

**Introduced by this round.** **Confidence:** confirmed

**Root:** class guard keyed on incidental syntax

## Checked and found correct

- **The `dco.sh` rewrite itself.** `signoff_addresses()` extracts the address with `sed` and
  the caller compares it with `grep -qxF`, so no value reaches a pattern language; case is
  folded on both sides; the here-document keeps `failed` in the current shell, and the trailing
  blank line a here-document adds is absorbed by `[ -n "$sha" ] || continue`. The refusal for
  an unresolvable range names `git fetch` and both remote spellings. Reverting the script turns
  exactly the three new tests red and leaves the six older ones green — both directions held.
- **`set -o pipefail` over `signoff_addresses | grep -q` is not a hazard in practice.** The
  classic trap (grep exits on the first match, the producer takes SIGPIPE, pipefail returns
  141, an honest sign-off is refused) was reproduced for: a commit whose message is 200 KB with
  the sign-off near the top. `rc=0`, `all commits … are signed off`. The output of
  `signoff_addresses` is a few bytes and never fills a pipe buffer, so the producer always
  finishes first.
- **The scenario-count pair.** Exact equality is the right call and the refusal names the
  command and the three files; the second test is real — reverting `scenario_count()` to
  `unittest.defaultTestLoader` turns it red (`0 != 341`), because the shared loader carries
  `-k` patterns. The documents say 341 and the suite has 341.
- **`CommandSweepRuleTest` as a rule over the suite.** Fed the suite at `d33527c` it names
  exactly the defective sweep and nothing else; fed the suite at HEAD it is quiet; the invented
  honest forms (a sweep asking through the shared helper, a sweep with its own copy of the
  vocabulary, a two-command loop) are not flagged. The shape holes are R2-009, not this.
- **`BODY_ARGV` moved to module level and shared by both sweeps.** The two sweeps can no longer
  disagree about what "the command did not start" means, and the table's coverage of the tool's
  command list is asserted in both. Named as an incidental fix in the report, with its test.
- **The CI guard's tightening, for everything except R2-003.** The program is compared by
  basename (the validator lives in a venv under `$RUNNER_TEMP`), the arguments in order, the
  commit range by shape; measured, the real workflow passes, the pip line does not masquerade
  as the validator, the `python3 -m venv` line does not masquerade as the suite, and both
  claimed deletions go red.
- **`ShellGateMutationTest`'s faithfulness.** Neither script depends on its own location, so a
  copy in a temporary directory behaves as the original; the copy is made executable, and the
  clean-copy control is a separate test. The mutation is `exit N` → `exit 0` on one line at a
  time and leaves a parsable script (`bash -n` rc 0 checked on the reverted `dco.sh`). The awk
  `exit(found ? 1 : 0)` inside `guard-grep.sh` is correctly *not* treated as a shell refusal
  and is held by the behavioural tests instead.
- **en ↔ ru parity of the round's own CHANGELOG entries.** Six bullets each, the same fourteen
  test and class names, the same numbers, every named test present in the suite. The glued
  paragraph is fixed in both files and the rule reports nothing on any of the twelve root
  documents.
- **The corrections written into the round-1 report** (T4-025) are notes placed beside the
  stale figures rather than silent edits, which is the right form: the report is the record of
  that round.
- **No second address for the glued-paragraph defect.** The rule applied to all 78 tracked
  `.md` files — role templates, assets, `examples/toy`, the review's own reports — reports
  nothing outside the two CHANGELOGs, which are fixed.

## Is another round needed

**Yes — for R2-001 and R2-002, both medium.** Not because the round was weak: the two gate
defects it was handed (T4-019, T4-026) were real, are fixed, and are now held by tests proven
red on the reverted script, and the CI-step guard went from "two words anywhere in the file" to
something that actually reads a `run:` body. The project is better in the places the fixes
touched.

What needs a round is that the bookkeeping fix went the wrong way. T4-020 said a class was
recorded as closed by a guard that does not close it; the fix wrote sixteen `rule` fields,
thirteen of them in other blocks' findings, and ten of the new values are green on the finding
they are recorded against — measured five times, three of them replacing a value that was
correct, and two of them contradicting the fixer's own table. `review roots` now advertises a
seven-instance root as closed by a guard that holds two of the seven. That is the same defect,
wider, in the register that is the review's memory, and it is the sort of thing a later reader
will trust rather than re-measure. R2-002 is smaller but concrete: one of the three commands
T4-023 named still does not reach a write.

**Where the findings sit:** all nine are inside code or records this fix round changed — five
in the guards it wrote (R2-002, R2-003, R2-004, R2-008, R2-009), two in the register it
rewrote (R2-001, R2-007), two in the documents it wrote about itself (R2-005, R2-006). None is
in the documents or the CI the block originally reviewed; those fixes are holding.

**The signal a human should read.** Two rounds in a row the top finding of this block is in the
same class — round 1's R1-002/R1-003 were "a guard recorded for a class that does not hold it"
and "a guard matching two words", and round 2's R2-001 is the first of those again, now made
worse by its own fix. The three rounds of guards-over-guards are producing guards faster than
they are producing coverage, and the tool cannot check the thing the register is being asked to
record: it stores a `rule` per finding but validates only that the path exists, and `roots`
prints one rule for a whole root, which is what let this pass. The fixer names this in "found,
not fixed" and calls it the lead's decision, and that is the right reading. **The next move is
not a third T4 fix round on the same guards: it is a decision about whether `check` should tie
a rule to the finding it closes** (a `review.py` change, block T1, closed) — and, failing that,
whether the `rule` field should simply be left at the guard the round measured rather than
re-pointed to make a printed line look tidy.

The seven low findings do not need a round: R2-001's register rows and R2-007's duplicate are
edits to `findings.jsonl`, and R2-003 through R2-009 are a few lines each in the guards.

## What was run

**The suite**, from the repository root, this tree otherwise idle:

```
$ python3 -m unittest discover -s tests
Ran 341 tests in 340.779s

OK
```

341 confirms the documents, and 340.779 s confirms "about six minutes" in README (both
languages) and AGENTS.md. The fixer's 330.661 s is the same measurement on the same machine.

**Targeted runs**, all of them listed in "What was checked and how": `DcoGateTest` on the
reverted script (3 red / 6 green), `IdempotenceTest` and `GuardGrepTest` and
`ShellGateMutationTest` on restored defects, `test_пороги_из_документов_читаются_из_кода` and
`test_число_сценариев_в_документах_равно_настоящему` on a restored README, `GateRegistryTest`
on a flipped `cmd_check` gate, and the rule helpers (`_gates_not_run`, `_glued_to_list_item`,
`_sweeps_without_body_check`, `_rules_without_samples`, `_workflow_steps`, `scenario_count`)
driven directly on invented and on reverted sources.

**The state of the tree afterwards.** `git status --porcelain` names only this report. Every
file written during a measurement (`README.md` once) was restored byte for byte and verified.

**`review check`** names no T4 finding; what is left for T4 is the two staleness lines the
fixer already flags as the lead's call. It does name `finding T2-020: code in CHANGELOG.md
changed since import` — R2-007.

**`.github/dco.sh d33527c..HEAD`** — the fixed gate over the commits that fixed it: exit 0,
`all commits in d33527c..HEAD are signed off`.
