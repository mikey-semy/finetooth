# T4 — Documentation and the repository contract · fix report, round 3

Eight findings handed over, **8 closed, 0 rejected, 0 deferred**. Every defect was reproduced
on the code as it stood before the fix; every fix carries a test proven red without it, and —
where the fix narrows something — a second test proving that what was allowed still passes.

Five of the eight sit in the guards the previous round had just written. Each was green on
exactly the state it exists to forbid, and each was measured green there before the fix: the
write-boundary sweep with the register write pointed outside `docs/review/`, the CI-gate rule
with the real workflow's test step neutralised, the shell-gate rule with a fourth gate script
added, the sweep rule with four evasions, the glued-paragraph rule with a numbered list.

**Per the maintainer's decision for this round, `set-finding --rule` was not called at all**
(T4-027, issue #28: it overwrites the guard field of other blocks' findings). The guard that
closes each class is named here in the report; the register's guard fields are the lead's to
repair after #28.

## Findings → verdict → commit

| Finding | Verdict | Commit | Guard (named here, not written to the register) |
|---|---|---|---|
| T4-028 · medium · the write-boundary sweep reached no write | closed | `fa7d460`, `e1ae630` | `WriteBoundaryTest::test_обход_доводит_до_записи_каждую_пишущую_в_реестр_команду` |
| T4-029 · low · a CI step counted while the gate could not fail | closed | `9d506ea` | `RepositoryContractTest::test_узда_видит_обезвреженные_ворота` |
| T4-030 · low · the glued-paragraph rule knew one kind of list | closed | `3fe7eec` | `RepositoryContractTest::test_узда_видит_абзац_приклеенный_к_пункту` |
| T4-031 · low · the CHANGELOG's count of a round | closed | `0dd1dd6` | — (no sound guard exists; see "Found, not fixed") |
| T4-032 · low · the round-2 report's count of new tests | closed | `0dd1dd6` | — (same class) |
| T4-033 · low · one defect, two register records | closed | `0aac6e0` | — (bookkeeping) |
| T4-034 · low · the shell-gate rule's hand-written list | closed | `9e45524` | `ShellGateMutationTest::test_каждые_ворота_на_оболочке_под_правилом` |
| T4-035 · low · the sweep rule satisfied by a name in the text | closed | `f44f3cf` | `CommandSweepRuleTest::test_узда_видит_обход_которого_ещё_нет` |

All guards live in `tests/test_review.py`.

---

## T4-028 · the write-boundary sweep started three commands and reached the write of none

**Probe before the fix.** Every subcommand run on `WriteBoundaryTest`'s own stand with the
arguments `BODY_ARGV` gives it, exit code and the argparse question printed side by side:

```
import       ('H1',)              rc=2 argparse='' err='error: no findings file for the block: docs/review/reports/H1-findings.jsonl'
restamp      ('H1',)              rc=2 argparse='' err='error: H1 is in status todo — nothing to stamp'
set-finding  ('H1-001', 'open')   rc=2 argparse='' err='error: finding H1-001 is not in the register'
```

Three of the commands that WRITE, refused before their write, with argparse silent — so the
sweep counted all three as exercised. The previous round had fixed the other half of exactly
this defect (argparse refusing before the body) and left this half standing.

**Mutation, before the fix.** The register write of each writing command redirected to
`ROOT / "leaked-findings.jsonl"` — a file outside `docs/review/`, which is precisely what
`SECURITY.md` promises never happens — one command at a time, the suite as it stood:

```
--- mutant-import --- rc=0        Ran 3 tests ... OK
--- mutant-set-finding --- rc=0   Ran 3 tests ... OK
--- mutant-restamp --- rc=0       Ran 3 tests ... OK
```

The guard of the promise was green on all three.

**What was done.** The stand is now part of the same contract as the argument table
(`body_stand`): a draft findings file imported into the register, so `set-finding` has a row
to move; a second, unnumbered finding left in the draft, so the sweep's own `import` has a
number to hand out; and the finding's file moved on after the import, so `restamp H1-001` has
a fingerprint to re-take. `BODY_ARGV["restamp"]` names a finding rather than a block, because
`set-status` runs earlier in the sweep and leaves the block in a status a block re-stamp
refuses. A refusal (exit 2) no longer counts as a pass, and the message says the stand is what
needs extending.

**After the fix**, the same three mutants:

```
--- mutant-import --- rc=1        Ran 5 tests ... FAILED (failures=7)
--- mutant-set-finding --- rc=1   Ran 5 tests ... FAILED (failures=4)
--- mutant-restamp --- rc=1       Ran 5 tests ... FAILED (failures=3)
```

Each mutant is an executable tool — the failures are the guard, not a broken build.

**Test that catches it.** `WriteBoundaryTest::test_обход_доводит_до_записи_каждую_пишущую_в_реестр_команду`
asserts that `import`, `set-finding` and `restamp` each change the register; the sweep itself
now also refuses exit 2 from any command.

**The other side.** `test_красный_приговор_ворот_за_несделанную_работу_не_считается`: exit 1
is a gate's verdict, not a refusal before work. Without it the sweep could be tightened into
demanding zero, and it would then go red on `check` and `coverage` over its own stand — and
the write boundary would have nothing holding it at all.

**Incidental fix, with its own test.** The first version of the register-change assertion
compared the file's bytes, and a re-import of the same draft within one second writes the same
bytes: the full suite went red once on `import` for that reason alone. A check whose verdict
depends on the clock proves nothing about the write. Each of the three commands now has work
whose result is visible in the register's content (`e1ae630`); the assertion is the test named
above, and it is the test that failed on the flake.

## T4-029 · a CI step counted as running a gate it had been made unable to fail

**Probe before the fix.** `_runs_command` asked directly:

```
'python3 -m unittest discover -s tests -k НетТакого || true'   -> True
'python3 -m unittest discover -s tests -k НетТакогоТеста'      -> True
'.github/dco.sh HEAD~1..HEAD'   (declared: origin/dev..HEAD)   -> True
```

`|| true` keeps the exit code away from CI; `-k` with a pattern matching nothing runs zero
tests; `HEAD~1..HEAD` checks one commit instead of the pull request's. Three ways to keep the
step and lose the gate, all counted as running it.

**Mutation on the real workflow.** `.github/workflows/tests.yml`, the test step rewritten to
`python3 -m unittest discover -s tests -v || true`, with the fix in place:

```
AssertionError: Lists differ: ['python3 -m unittest discover -s tests'] != []
 : CONTRIBUTING велит гонять эти команды, а ни один шаг рабочего процесса их не гоняет
FAILED (failures=1)
```

**What was done.** A step may add only arguments named as widening — `-v`, `--verbose`, each
addition to the list asking for the reason it does not narrow the gate — and on the place of a
declared commit range it may put the substitution CI takes from the event, or the declared
range itself, nothing else. GitHub Actions expressions are collapsed into one word first
(`_step_tokens`): `${{ github.sha }}` carries spaces, and split on them the range falls apart
into five words of which `}}..${{` is the one that looks like a range.

**Test that catches it.** `RepositoryContractTest::test_узда_видит_обезвреженные_ворота`.
On the reverted `_runs_command` (which builds and runs — it is the previous implementation
verbatim):

```
FAILED (failures=3)
  'python3 -m unittest discover -s tests || true' засчитан как прогон
  'python3 -m unittest discover -s tests -k НетТакогоТеста' засчитан как прогон
  '.github/dco.sh HEAD~1..HEAD' засчитан как прогон
```

**The other side.** The same test's `HONEST_STEPS` half: the validator called from a venv under
`$RUNNER_TEMP`, the commit range substituted from the event payload, the declared range spelled
out word for word, and a louder `-v` — all four still count, and stayed green through the
revert. `test_каждые_объявленные_ворота_гоняет_ci` on the real workflows is green.

## T4-030 · a paragraph is glued to a list item by the column its text starts at

**Probe before the fix.**

```
'1. item\nParagraph.\n'   -> []      (missed)
'1) item\nParagraph.\n'   -> []      (missed)
'- item\n Paragraph.\n'   -> []      (missed)
'- item\nParagraph.\n'    -> ['2: Paragraph.']
```

`RELEASING.md` is a numbered procedure end to end, and a paragraph written flush under step 4
joins step 4. Under `- item` the item's text starts at column 2, so a line indented by one
space is swallowed exactly as a flush one is; and a paragraph after a legitimate indented
continuation is swallowed too, which the rule also missed.

**What was done.** The opener is any bullet or number (`LIST_OPENER`), and what separates a
continuation from a paragraph is the column the item's text starts at — with CommonMark's rule
that more than four spaces after the marker start an indented block instead. A heading, a
quote, a table, a link reference definition and a horizontal rule close the item (`OWN_BLOCK`).

**Test that catches it.** `RepositoryContractTest::test_узда_видит_абзац_приклеенный_к_пункту`,
four shapes added. On the reverted `_glued_to_list_item`:

```
FAILED (failures=5)
  разметка='абзац под нумерованным пунктом'        узда не увидела приклеенный абзац
  разметка='абзац под пунктом со скобкой'          узда не увидела приклеенный абзац
  разметка='отступ меньше колонки текста пункта'   узда не увидела приклеенный абзац
  разметка='абзац после продолжения пункта'        узда не увидела приклеенный абзац
  невиновный='горизонтальная черта'                Lists differ: ['2: ---'] != []
```

The fifth is the old implementation's false positive in the other direction: a `---` under a
list item was reported as a glued paragraph. The new shape reads it as its own block, and the
innocent half of the table holds that.

**The other side.** `NOT_GLUED_SHAPES` grew with an indented continuation of a numbered item,
the next numbered item, a table row, a horizontal rule, and a paragraph separated from a
continuation by a blank line. All green.

**Incidental fix, with its own test.** The rule ran over root-level `*.md` only. It now runs
over every tracked `.md` except `docs/review/` — the role templates are numbered lists of rules
an agent works by, and a paragraph that slides inside rule 4 changes its meaning there just as
much. Measured by planting a glued paragraph in `skills/finetooth/references/fix.ru.md`:

```
посажено в skills/finetooth/references/fix.ru.md на строке 10
новый охват : (1, "AssertionError: Lists differ: ['10: Приклеенный абзац.'] != [] | FAILED")
старый охват: (0, 'OK')
```

The test is `test_в_документах_нет_абзаца_приклеенного_к_пункту_списка`, whose file list is the
thing the probe changes. Across all 79 tracked `.md` the new rule finds two live occurrences,
both inside `docs/review/` — see "Found, not fixed".

## T4-031 · the CHANGELOG's count of a round disagreed with the register

**Probe before the fix.** The register against the paragraph:

```
CHANGELOG.md:102  "The fix review of block T4, six more findings, all closed here"
register          T4-019 … T4-026 — eight, all fixed
                  T4-020 and T4-025 appear in no entry of that list
```

Release notes are taken from this section verbatim (RELEASING gate 4), and the neighbouring
block paragraphs use the register's count, so the reader has no way to tell which is wrong.

**What was done.** Both languages now say eight, the split between guards and documents is
restated to match (five in the guards and the gate, three in the documents, the register and
the round's own report), and entries for T4-020 and T4-025 are written in both CHANGELOGs.

**Test that catches it.** None — see "Found, not fixed": the class has no guard that would be
sound, and inventing one would be worse than saying so.

## T4-032 · the round-2 fix report's count of its own new tests

**Probe before the fix.** The suite counted at both ends of the round, with its own loader
(the one `scenario_count()` uses, so `-k` cannot skew it):

```
d33527c scenarios: 325        # the commit the round started from
HEAD    scenarios: 341
                              # sixteen, against the report's "twenty-three new tests"
```

The `git diff` count of `def test_` lines is not the measurement and does not agree with it
either: the suite's own invented sweeps contain `def test_x` inside string literals.

**What was done.** Both places in the report that stated the figure — the "Nothing else"
paragraph and the "What was run" section — now state sixteen and where the number comes from.

## T4-033 · one defect, two register records

**Probe before the fix.**

```
$ review check
  · finding T2-020: code in CHANGELOG.md changed since import — re-check …
$ review findings
  T2-020  open  low  CHANGELOG.md  the T2 section's opening paragraph follows the last T4 bullet …
  T4-022  fixed low  CHANGELOG.md  the T2 section's opening paragraph is swallowed into the preceding T4 bullet …
```

The same paragraph in the same two files, found one round apart, fixed once. `check` was red on
a defect that no longer exists, and a block's fixer was being offered a finding with nothing
behind it.

**What was done.** `set-finding T2-020 duplicate --dup-of T4-022`. This is the one register
record of another block this round touches, and the maintainer's decision names it explicitly:
`--dup-of` writes one row, unlike `--rule`, which writes a whole root.

**After the fix**, `review check` no longer mentions T2-020.

## T4-034 · the shell gates under the mutation rule are the ones git lists

**Probe before the fix.** The rule's subject beside git's:

```
GATES (hand-written)                       .github/dco.sh, skills/finetooth/assets/guard-grep.sh
git ls-files '*.sh', scripts with refusals .github/dco.sh                          [51, 84]
                                           skills/finetooth/assets/guard-grep.sh   [49, 55, 59, 76]
                                           skills/finetooth/assets/run-role.sh     [22]
```

`run-role.sh` was outside the rule: its refusal on an unknown role is held by a test, but by
nothing that would notice if the test went away.

**Mutation.** A fourth gate script added and tracked — two refusals, no test:

```
новое правило   : (1, "AssertionError: Lists differ: ['.github/fourth-gate.sh'] != [] | FAILED")
правило до круга: (0, 'OK')
```

**What was done.** `GATES` is checked against `git ls-files` in both directions: a tracked
script with a refusal that names no test fails the rule, and a script named in the list with no
refusals left fails it too. `run-role.sh` joins the list, and the tests that hold its refusals
take the script through `shell_gate`, so the substituted copy is what they run. Because that
script calls `axes.py` by a path from itself, the copy is made inside a mirror of the skill
directory (`NEIGHBOURHOOD`) — a copy that cannot find its neighbour would go red from the
missing neighbour and the mutation would prove nothing.

**Incidental fix, with its own test.** The shape of a refusal was recognised only at the start
of a line or after `;`. `if …; then exit 3; fi` and `check || exit 5` are how refusals are
ordinarily written, and `run-role.sh`'s refusal on a lost journal line (`exit 3`, line 66) is
written the first way — outside the rule as well:

```
before: skills/finetooth/assets/run-role.sh  refusals=[22]
after : skills/finetooth/assets/run-role.sh  refusals=[22, 66]
```

Four new shapes are in `REFUSAL_SHAPES`; the other direction is in `INNOCENT_SHAPES`, which
grew a whole-line comment explaining an exit code (both scripts do that in prose right beside
the code) and `exit "$RC"`, a pass-through rather than a refusal.

**Test that catches it.** `ShellGateMutationTest::test_каждые_ворота_на_оболочке_под_правилом`
for the list, `test_каждый_отказ_скрипта_держит_тест` for the refusals (now 8 mutants across
three scripts, each silenced in turn, each making its named test red),
`test_узда_видит_отказ_которого_ещё_нет` for the shape in both directions.

**The other side.** `test_на_целой_копии_прогон_ворот_зелёный`: the substituted copy of each
of the three scripts, unmutated, leaves its named tests green. This is the test that caught
the `axes.py` neighbour problem — without `NEIGHBOURHOOD` it went red on the clean copy, which
would have made every "the suite went red" below meaningless for that script.

## T4-035 · a sweep counts as checked when it asks in code and asserts on the answer

**Probe before the fix.** Three invented sweeps, none of which checks anything:

```
докстрока (the helper's name in a docstring only)   -> []
мёртвое присваивание (argparse_refused = None)      -> []
звёздочка (self.s.run(*[cmd]))                      -> []
```

A fourth was found while fixing it: a sweep that calls `argparse_refused(out.stderr)` and
throws the answer away.

**What was done.** The command list must come from the tool in CODE (`--help` as a call
argument, or `_subcommands()`), the command must be one the sweep was given (a starred argument
counts), and the refusal vocabulary — the shared helper or a sweep's own walk of
`ARGPARSE_REFUSED` — must be reached from inside an assertion.

**Test that catches it.** `CommandSweepRuleTest::test_узда_видит_обход_которого_ещё_нет`,
four shapes added. On the reverted `_sweeps_without_body_check` (which builds and runs):

```
FAILED (failures=4)
  обход='вопрос только в докстроке'                  Lists differ: [] != ['test_x']
  обход='мёртвое присваивание вместо вопроса'        Lists differ: [] != ['test_x']
  обход='вопрос без проверки'                        Lists differ: [] != ['test_x']
  обход='имя команды через развёртывание списка'     Lists differ: [] != ['test_x']
```

**The other side.** `INNOCENT_SWEEPS` grew a sweep that runs the command through a starred list
AND asks properly, and a test whose docstring talks about `--help` and `_subcommands` without
being a sweep — the shape the stricter detection must not start flagging. Both stayed green
through the revert, and the two sweeps the suite actually has are unaffected.

---

## Found, not fixed

**A guard for "a number in a public document not checked against its source" cannot be written
soundly for T4-031 and T4-032.** The class already carries a guard in the register
(`test_число_сценариев_в_документах_равно_настоящему`), and it covers the numbers whose source
the repository can read: the scenario count, and the `coupling` thresholds via
`test_пороги_из_документов_читаются_из_кода`. The two new instances are counts of a ROUND — the
findings closed in one fix review, the tests added in one range — and the register has no
notion of a round: it stores a block and a status, not which pass produced a row. A guard
comparing "eight findings" to the register would have to guess, and the paragraphs it would
check mean different things (block T1's count is all of the block's findings, T2's is those
closed in that entry, T4's is a round's). The shape of a real fix is known and is the lead's:
either the register gains a round, or the CHANGELOG paragraph names the ids it counts.
Not invented here, because a guard that guesses is the defect this block exists to find.

**Two live glued paragraphs, both inside `docs/review/`.** Scanned with the new rule over all
79 tracked `.md`:

- `docs/review/reports/T1-tool.fixreview-5.md:318` and `:319`
- `docs/review/reports/T1-tool.verify.md:324`

These are the records of block T1's rounds, deliberately outside the rule: the review directory
is deleted when the review closes, and its reports are not rewritten. Named for the lead in case
either report is ever published.

**A finding whose file is the register can never be stamped clean.** `restamp T4-027` reports
the fingerprint re-taken, and `check` is red on T4-027 again immediately: `file_sha` reads the
file before the restamp's own write to it, and the finding's file is
`docs/review/findings.jsonl` itself. So a deferred finding ABOUT the register keeps `check` red
for the rest of the review whatever anybody does. Tool defect, block T1 is closed, and it
belongs with issue #28, which is about the same command.

**Other blocks' findings gone stale in the file this round changed.** `check` names
`T1-066` (deferred), `T2-016` and `T2-019` (open) as stale on `tests/test_review.py`; they were
stale before this round and are more so now. `T1-038`, `T1-048`, `T1-064` are stale on
`skills/finetooth/scripts/review.py`, which this round did not touch. Left alone: moving another
block's record is what T4-027 was raised about.

**The four block-staleness lines** (`T1`…`T4`: block files changed after the review) are
unchanged from the previous round: re-stamping a block after a fix review is the lead's call.

## Observations outside the assignment

- **`_shell_gates` still cannot see two refusal shapes** it would be reasonable to write:
  `exit` with a variable code (`exit "$RC"` — deliberately excluded, it is a pass-through) and a
  refusal produced by a function called for its exit code rather than by `exit` at all. Neither
  occurs in the three scripts today. Recorded rather than widened further: the round's rule says
  a defect of a different kind is a finding, not a fix inside somebody else's.
- **`skills-ref` is not installed on this machine.** The skill format was validated with the
  throwaway venv the previous round left behind, built from the commit `.github/workflows/tests.yml`
  pins (`69ef37e…`). Same validator, same version; noted because the command in CONTRIBUTING
  assumes it is on `PATH`.
- **The suite's wall clock.** 345 tests in 352s on this machine, with the tree otherwise idle —
  README and AGENTS.md say about six minutes, CONTRIBUTING about five, and the measurement sits
  between them, as it did last round.

## Rejected and deferred findings

None. All eight findings reproduced on the current code.

## What was run

The full gates, once, at the end of the series; the relevant suite after each fix.

```
$ python3 -m unittest discover -s tests
.........................................................................................
----------------------------------------------------------------------
Ran 345 tests in 352.871s

OK
```

**Four of those 345 are this round's**: the suite ran 341 at `fc71cb0`, where the round began,
and 345 at its end, both counted with `scenario_count()`'s own loader. Four rather than more
because most of this round's work tightened existing rules, and a tightened rule grows by rows
in its own table — subtests, which are not scenarios. The four new scenarios are the
write-boundary pair (`test_обход_доводит_до_записи_каждую_пишущую_в_реестр_команду`,
`test_красный_приговор_ворот_за_несделанную_работу_не_считается`), the neutralised-gate table
(`test_узда_видит_обезвреженные_ворота`) and the shell-gate coverage rule
(`test_каждые_ворота_на_оболочке_под_правилом`). The public count was updated to 345 in
README (both languages) and AGENTS.md — the exact equality that round 2 restored makes that a
required edit, not an optional one.

```
$ skills-ref validate skills/finetooth
Valid skill: skills/finetooth
(rc=0; validator from the venv built at the commit tests.yml pins)
```

```
$ python3 skills/finetooth/scripts/review.py check
  (T4: no open finding, no stale finding except T4-027 — see "Found, not fixed")
  (the rest is other blocks' findings and the four block-staleness lines, unchanged)
```

Per-fix runs, each after its own commit:

```
-k WriteBoundaryTest -k HandWrittenInputTest     Ran 16 tests ... OK
-k CommandSweepRuleTest                          Ran  2 tests ... OK
-k RepositoryContractTest                        Ran 16 tests ... OK
-k ShellGateMutationTest                         Ran  4 tests ... OK
```

Every mutation in this report was taken with this tree otherwise idle, and every file written
during a measurement was restored and checked with `git status --porcelain`.
