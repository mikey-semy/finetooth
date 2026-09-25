# T4 — fix review, round 3

Diff `fc71cb0…HEAD` (157 KB, 1461 lines, 11 commits `fa7d460…0ae0e3a`) read in full. No
`--scope` split was needed.

## What was checked and how

**Baseline.** `python3 -m unittest discover -s tests` → `Ran 345 tests in 340.537s / OK`.
The figure in `README.md`, `README.ru.md` and `AGENTS.md` equals it. The round's arithmetic
checks out independently: `unittest.TestLoader().discover()` on `tests/test_review.py` at
`fc71cb0` counts **341**, at `HEAD` **345**, and the diff adds exactly four `def test_` —
the four the report names. `review check` shows no open and no stale T4 finding except
`T4-027`, exactly as the report discloses.

**Every fix proven by reverting**, one mechanism at a time, the rest of the round left in
place, `ast.parse` run on each reverted tree so a green run cannot mean "it did not build":

| reverted | test that must go red | result |
|---|---|---|
| `_runs_command` | `test_узда_видит_обезвреженные_ворота` | **red, 3 subtests** — `\|\| true`, `-k`, `HEAD~1..HEAD`; the honest half and `test_каждые_объявленные_ворота_гоняет_ci` stayed green |
| `_glued_to_list_item` | `test_узда_видит_абзац_приклеенный_к_пункту` | **red, 5 subtests** — four missed shapes plus the old false positive on `---` |
| `_sweeps_without_body_check` | `test_узда_видит_обход_которого_ещё_нет` | **red, 4 subtests** — the four evasions |
| `SHELL_REFUSAL` + `_shell_gates` | `test_узда_видит_отказ_которого_ещё_нет` | **red, 4 subtests** — `then exit`, `else exit`, `\|\| exit`, bare `case` branch |

**Gates checked by violation, not by reading** (rule 7):

- *Shell-gate coverage.* A fourth tracked gate script (`.github/fourth-gate.sh`, two
  refusals, no test) → `test_каждые_ворота_на_оболочке_под_правилом` **red, naming the
  script**; with the pre-round `_shell_gates`/`SHELL_REFUSAL` in place the same violation
  was **green**. Removed afterwards.
- *Document file list.* A paragraph glued under rule 1 of
  `skills/finetooth/references/fix.md` → `test_в_документах_нет_абзаца_приклеенного_к_пункту_списка`
  **red, naming the file** — a file the pre-round pathspec (`:(glob)*.md`, root only) did
  not look at. Restored afterwards.
- *Public scenario count.* `README.md` set to 344 →
  `test_число_сценариев_в_документах_равно_настоящему` **red**, and the message names the
  command and all three files. Restored afterwards.

**The write-boundary guard measured from both sides** — the round's heaviest claim, and the
one that stands behind `SECURITY.md`. Each register write of the tool redirected in turn to
`ROOT / "leaked-*.jsonl"` in a copy of the skill (`FINETOOTH_TOOL`), then
`test_ни_одна_команда_не_пишет_вне_каталога_ревью` run on that copy:

```
                         pre-round guard (fc71cb0)     guard at HEAD
cmd_import      (2144)   OK   (leak invisible)         FAILED (failures=3)
cmd_set_finding (2223)   OK   (leak invisible)         FAILED (failures=1)
restamp_finding (2451)   OK   (leak invisible)         FAILED (failures=1)
```

That is a real repair of a real hole, proven in both directions. The same measurement then
turned up two register writes the round did not visit — R3-001 below.

**What I did not do.** `skills-ref validate` was not run: `skills-ref` is not on this
machine's `PATH`, and I did not rebuild the venv the fixer's report describes — so the
skill-format claim in that report rests on their measurement, not mine. Nothing in this
round touches `skills/finetooth/` except a role template I planted a probe in and restored,
so I do not expect the format to have moved. The round makes no claim reproducible against
a running service, so rule 8 does not apply here beyond the mutation runs above.

**Rule 6 (incidental fixes).** Four changes in the diff are not in the finding list; all
four are named in the fixer's report with their own tests: the register-content assertion in
`body_stand` (`e1ae630`), the widened `OWN_BLOCK` closing the old `---` false positive, the
widened refusal shapes reaching `run-role.sh:66`, and the widened document file list.
The hoist of `_tracked` to a module-level `tracked()` is a pure move (the body is byte-identical,
`_tracked = staticmethod(tracked)` keeps the old name) — a refactor, not an unnamed fix.
`restamp T4-027` and `set-finding T2-020 duplicate --dup-of T4-022` both touch the register
and both are disclosed in the report. I found no fix in the diff that the report does not
mention, and no test the report claims that is not in the diff.

## Findings

### R3-001 · medium · the write-boundary sweep reaches the register write of three commands out of five

**Location:** `tests/test_review.py:3462` (`REGISTER_WRITERS`), `tests/test_review.py:3411` (`ARGV`)

**What is wrong:** the round closed T4-028 by driving `import`, `set-finding` and `restamp`
to their register writes, and recorded the subject as a hand-written tuple of those three.
Two other commands write `findings.jsonl` — `cmd_backfill` (`review.py:2581`) and `cmd_init`
(`review.py:650`) — and the sweep reaches neither. `backfill` runs on the new stand, finds
every fingerprint already in place, prints `fingerprints are in place — nothing to stamp`
and returns **before** its write; `init`'s `FINDINGS_FILE.touch()` is reached, but `setUp`
has already run `init` once, so its file exists before `before = self._snapshot()` is taken
and a `touch` changes no bytes. This is the same defect T4-028 names, at the two addresses
the fix did not visit, and the new list of writers is hand-written in exactly the way
`ShellGateMutationTest.GATES` was before T4-034 took it from `git ls-files`.

**Failure scenario:** redirect `cmd_backfill`'s register write to
`(ROOT / "leaked-backfill.jsonl").open("w")` — a file outside `docs/review/`, which
`SECURITY.md` promises never happens — and run the guard on that copy of the tool:

```
--- leak via backfill (2581)    rc=0  Ran 1 test in 5.044s  OK
--- leak via init touch (650)   rc=0  Ran 1 test in 5.047s  OK
```

Both green, where the same probe against `import`, `set-finding` and `restamp` is red three
times over. A future `--out`-style flag on `backfill`, or a `backfill` that starts writing
its own report, passes a guard whose docstring says a new command falls under it by itself.

**Why it is a defect:** invariant 1 (the gate must not be satisfiable without the state it
asserts) and invariant 7 (only `docs/review/` is written) — the SECURITY.md promise is held
for three of the five commands that write the register. Fix-review rule 5: the fix went to
three addresses of the defect and not to the other two.

**Introduced by this round or present before:** the hole in `backfill`/`init` was present
before; the round's fix and its new positive test were the occasion to close it and did not.
`REGISTER_WRITERS` itself is this round's.

**Confidence:** confirmed (measured above).

**Root:** guard enumerates its subject without exercising it

---

### R3-002 · medium · a CI step is still counted as running a gate it has been made unable to fail

**Location:** `tests/test_review.py:5749` (`_runs_command`), `tests/test_review.py:5705` (`_workflow_steps`)

**What is wrong:** T4-029's fix narrowed the comparison of a declared command against a
step's *command line*. But a step is not a command line: it is a YAML mapping with a `run:`
block, and `_workflow_steps` hands `_runs_command` **one line at a time**. Everything that
neutralises a step from outside that one line is invisible — the two canonical GitHub
Actions forms (`continue-on-error: true`, `if: false`) and any neighbouring line of the same
`run:` block. The rule's own comment says "a step may add only arguments named as widening";
what the code enforces is "some line of the step may".

**Failure scenario:** the real `.github/workflows/tests.yml`, the `Run the tests` step
rewritten each of four ways, `_gates_not_run` asked about the three commands `CONTRIBUTING.md`
declares:

```
|| true                         -> ['python3 -m unittest discover -s tests']   (caught)
-k NoSuchTest                   -> ['python3 -m unittest discover -s tests']   (caught)
continue-on-error: true         -> []                                          (green)
if: false                       -> []                                          (green)
run: |  set +e / <suite> / echo done   -> []                                    (green)
run: |  <suite> / exit 0               -> []                                    (green)
```

With `continue-on-error: true` on that step the suite can fail on every pull request, the
`tests` workflow reports success, branch protection is satisfied, and
`test_каждые_объявленные_ворота_гоняет_ci` — the guard of the root *a rule declared enforced
with nothing enforcing it* — stays green. That is precisely the scenario T4-021 was raised
for, restored by a one-line YAML edit.

**Why it is a defect:** invariant 1. Fix-review rule 5 — the same question ("can this step
still fail CI?") is asked in the run body and in the step's own keys, and the fix answered it
in one place.

**Introduced by this round or present before:** present before; this round narrowed the rule
against three shapes and left the two most idiomatic ones, which makes the rule read as
complete when it is not.

**Confidence:** confirmed (measured above).

**Root:** class guard keyed on incidental syntax

---

### R3-003 · low · the glued-paragraph rule misses a paragraph that opens with a link, and a list marker separated by a tab

**Location:** `tests/test_review.py:5790` (`OWN_BLOCK`), `tests/test_review.py:5787` (`LIST_OPENER`)

**What is wrong:** `OWN_BLOCK` treats any line starting with `[` as its own block, because a
link reference definition (`[0.8.0]: https://…`) is one. An ordinary paragraph that opens
with a link — `[Block T2](…) of the same review — …` — is the same shape and is skipped.
`LIST_OPENER` requires one or more **spaces** after the marker, so `-\titem`, a valid list
item, is not recognised as one at all.

**Failure scenario:**

```
'- item\n[Block T2](x) of the same review.\n'  -> []   (missed)
'-\titem\nParagraph.\n'                        -> []   (missed)
'- item\n**Block T2** of the same review.\n'   -> ['2: …']   (caught — the bold form works)
```

A CHANGELOG entry whose next paragraph begins with a link is swallowed into the preceding
bullet exactly as T4-022's did, and RELEASING gate 4 takes that section verbatim into the
release notes. No live occurrence today.

**Why it is a defect:** the same defect class the rule exists to close, at shapes the
widened rule still does not see. Not a style point: the failure is a wrong rendering of a
public release note.

**Introduced by this round or present before:** the round rewrote this rule; `[` as an
own-block opener is this round's addition, so the link case is new, and the tab case is
pre-existing and untouched.

**Confidence:** confirmed (measured above).

**Root:** class guard keyed on incidental syntax

---

### R3-004 · low · the command-sweep rule is still satisfied by a dead name, and does not see a sweep that walks the shared table

**Location:** `tests/test_review.py:5458` (`_asserts_the_command_started`), `tests/test_review.py:5422` (`_asks_the_tool_for_commands`)

**What is wrong:** the round closed "a dead `argparse_refused = None` satisfies the rule" by
requiring the name inside an assertion. A dead assignment **plus** an assertion about it
passes — one line more than the evasion the round measured. And the rule only recognises a
sweep when it calls `--help` or `_subcommands()`; a sweep that walks `BODY_ARGV` — the
shared table this very round made the contract for both existing sweeps — is not seen as a
sweep at all.

**Failure scenario:** four invented sweeps, none of which checks that any command started,
fed to `_sweeps_without_body_check`:

```
argparse_refused = '' ; for cmd in self._subcommands(): self.s.run(cmd)
                        self.assertFalse(argparse_refused)          -> []  (not flagged)
for cmd in BODY_ARGV: self.s.run(cmd)                               -> []  (not flagged)
for cmd in self.every_subcommand(): self.s.run(cmd)                 -> []  (not flagged)
self.assertTrue(argparse_refused or True)  (vacuous assertion)      -> []  (not flagged)
```

In the other direction the rule now flags an honest sweep that checks the answer with
`if said: raise AssertionError(said)` instead of a `self.assert*` call — a false refusal,
though one whose message names the fix.

**Why it is a defect:** invariant 1 as applied to the guard. The round's own CHANGELOG entry
says "the question is looked for in the syntax now, and the answer must be reached from
inside an assertion" — which is true and still leaves the dead-name evasion open one edit
away.

**Introduced by this round or present before:** introduced by this round (the rule is a
rewrite).

**Confidence:** confirmed (measured above).

**Root:** class guard keyed on incidental syntax

---

### R3-005 · low · the journal line of this round names the wrong role

**Location:** `docs/review/journal.md:44`

**What is wrong:** the line committed in `0ae0e3a` reads

```
· `T4` — fixreview round 3 — 8 findings closed, 0 rejected, 0 deferred; report T4-repo-contract.fix-3.md; …
```

This is the **fix** round 3 — it closes the findings of fix review round 2 — and it says so
by citing `fix-3.md`. Every other such line in the journal names the role it was
(`— fix — 18 findings closed, 0 rejected`, `— Fix phase round 2 (the findings of fix review
round 1)`), and the spend line the runner wrote immediately after this one is labelled
`fix`. A fix review does not close findings; it opens them.

**Failure scenario:** the journal is the review's memory on disk, and `git log` on
`docs/review/` is what the README says tells you what happened. A reader reconstructing the
rounds reads "fixreview round 3 closed 8 findings", looks for the fix round that did the
work, and finds none — and the next `fixreview` line, when round 4 writes one, will be the
second line in the file with that label for a different role.

**Why it is a defect:** it is the round's own record misstating the round — the same family
as T4-025 and T4-032, which this round closed.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed.

**Root:** the round's own record disagrees with the round

---

### R3-006 · low · the CHANGELOG counts the second fix review at eight findings where the register holds nine

**Location:** `CHANGELOG.md:113`, `CHANGELOG.ru.md:113`

**What is wrong:** "The second fix review of block T4, eight more findings, all closed
here." The register holds nine findings from that round — `T4-027`…`T4-035` — of which eight
are `fixed` and `T4-027` is `deferred` to issue #28. The preceding paragraph uses the same
construction for a round where the count and the closures happened to coincide, so a reader
has no way to read "eight" as "eight of nine".

**Failure scenario:** release notes are taken from this section verbatim (RELEASING gate 4).
A reader reconciling the release with the register counts nine records tagged *fix review
round 2* against a paragraph saying eight — the same reconciliation failure T4-031 was
raised for, on the paragraph written to close it. The deferred medium finding, the one thing
in that round still outstanding, is the one the paragraph omits.

**Why it is a defect:** a finding count is a number that must agree with its source; the
fixer's own report states the round's standard as "the register closes eight", and the
register's own count of the round is nine. The honest form costs six words: "nine more
findings, eight closed here and one deferred to #28."

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed.

**Root:** a number in a public document not checked against its source

## Checked and found correct

- **The write-boundary repair itself.** Measured from both sides (table above): the
  pre-round guard was blind to all three leaks, the guard at HEAD is red on all three. The
  `body_stand` design is right — each of the three commands is left work whose result shows
  in the register's *content*, not in a timestamp, so "the register did not change" cannot
  mean "it rewrote the same bytes". The fixer's report names the flake that taught them
  this, with its own commit.
- **Not demanding exit 0.** `test_красный_приговор_ворот_за_несделанную_работу_не_считается`
  is the right other direction: a gate's verdict (`check`, `coverage` on a red state) is work
  done, and without that test the sweep would have been tightened into going red on its own
  stand.
- **`body_stand` added to `HandWrittenInputTest`.** I checked this does not soften the
  no-traceback sweep: that sweep runs on a *damaged* `blocks.json`, where an early refusal is
  the correct behaviour, so it rightly does not inherit the `rc != 2` rule; the richer stand
  only drives the commands further into their own code before they meet the damage.
- **`_runs_command` against the real workflows.** The stricter rule does not go red on
  anything the repository actually has: the validator invoked by absolute path from a venv,
  the DCO range substituted from the event payload, and `-v` on the suite all still count.
  `${{ … }}` collapsed to one token before splitting is the right call — split on spaces the
  range falls apart into five words.
- **`run-role.sh` brought under the shell-gate rule.** Its two refusals (lines 22 and 66) are
  now mutants of `test_каждый_отказ_скрипта_держит_тест`, and the whole suite is green, which
  means each of the eight mutants across the three scripts made its named test red. The
  `NEIGHBOURHOOD` copy is necessary and is itself held by
  `test_на_целой_копии_прогон_ворот_зелёный` — without it "the suite went red" would have
  meant "the copy cannot find `axes.py`". The exclusion of `exit "$RC"` as a pass-through is
  correct and is disclosed in the report.
- **`T2-020 → duplicate --dup-of T4-022`.** The right call and the minimal one: it writes one
  row, `check` is no longer red on a defect that does not exist, and the report says why this
  and not `--rule` under the maintainer's decision for the round.
- **en ↔ ru parity.** Both new CHANGELOG sections have the same ten lines, the same seven
  bullets in the same order, and the same numbers (eight, five, four, 325, 341, twenty-three
  / двадцать три). `README.md`, `README.ru.md` and `AGENTS.md` all say 345, including the
  "What is inside" inventory line in both languages.
- **The "Found, not fixed" section.** The three things it declines to fix are declined for
  good reasons and each is named for the maintainer: a guard for a round's finding count
  cannot be written against a register that has no notion of a round; the two live glued
  paragraphs sit inside `docs/review/`, which is deleted when the review closes; and
  `restamp` on a finding whose file *is* the register can never come out clean. I reproduced
  the last one — `check` is red on `T4-027` on a clean tree — and it is a tool defect of a
  closed block, correctly routed to issue #28 rather than patched here.

## Is another round needed

**Yes by the letter of rule 11 — two medium findings — and the two fixes are small and
well-scoped:** derive `REGISTER_WRITERS` from the tool the way `GATES` is now derived from
`git ls-files` (R3-001), and give `_runs_command` the whole step, YAML keys included, instead
of one line of it (R3-002). Both are half a day at most and both close a real hole in a
guard that stands behind a published promise.

**But say the rest plainly.** Of my six findings, **six sit inside the code this round
changed** and none outside it. That is close to tautological — the round changed almost
nothing else — which is itself the signal: three rounds running, the block's work has been
guards on guards, and the top findings have landed in the same two classes every time.

- *class guard keyed on incidental syntax*: T4-021 (round 1) → T4-029, T4-030, T4-034,
  T4-035 (round 2) → R3-002, R3-003, R3-004 (round 3).
- *guard enumerates its subject without exercising it*: T4-023 (round 1) → T4-028 (round 2)
  → R3-001 (round 3).

Both classes have produced a finding in three consecutive rounds, each time inside the
previous round's own changes. By the measure rule 11 names, **the next move is a human's,
not another round.** This is the shape block T1 hit at rounds 4–7, where each round derived
the rule from the last defect and reopened an earlier one until the lead replaced point
fixes with a behavioural table (journal, 2026-09-24T19:53:55Z; issues #9 and #17). The same
remedy fits here: the two guards in R3-001 and R3-002 should each get one table of what
counts and what does not — every command the tool has that writes the register, taken from
the tool; every way a CI step can be kept and its verdict lost, taken from the Actions
documentation — rather than a fourth pass of "the shape we missed last time".

Recommendation: **one bounded round 4 for R3-001 and R3-002 written as tables, not as
patches**, with R3-003…R3-006 folded in as bookkeeping for the fixer or the lead; and if
that round produces a fifth finding in either class, close the block and file the class,
as T1 did.

The three low findings about documents (R3-005, R3-006) and the two guard gaps (R3-003,
R3-004) do not on their own justify a round.

**What got better.** The round did real work and I could measure all of it. The
write-boundary guard now actually guards the `SECURITY.md` promise for the three commands it
names — it did not before, in either direction. The CI rule now catches the three
neutralisations it was raised for. The shell-gate rule takes its subject from git and
covers a third script and two more refusal shapes. The glued-paragraph rule covers numbered
lists, indentation by column, and every tracked document rather than the root. Four new
scenarios, 341 → 345, the public number equal to the measurement in all three files, and no
regression anywhere in the suite. Nothing in this round broke anything that was working.
