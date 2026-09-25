# T4 — Documentation and the repository contract · fix report, round 2

Eight findings handed over, **8 closed, 0 rejected, 0 deferred**. Every defect was reproduced
on the code as it stood before the fix; every fix that could be tested carries a test proven
red without it, and — where the fix narrows something — a second test proving that what was
allowed still passes.

Five of the eight sat in the guards and the gate block T4 itself added in round 1, and that is
where the work of this round went: a gate that refused honest work and passed unexamined work,
and three guards that were green on exactly the state they were written to forbid.

## Findings → verdict → commit

| Finding | Verdict | Commit | Guard |
|---|---|---|---|
| T4-019 · medium · unescaped address in `dco.sh` | closed | `f9adc2f` | `DcoGateTest` (9 tests) |
| T4-026 · medium · `dco.sh` green on an unresolvable range | closed | `f9adc2f` | `ShellGateMutationTest` |
| T4-020 · medium · the register's guard for two classes | closed | `4ab7c1e` | — (bookkeeping; see below) |
| T4-021 · medium · CI-gate guard keyed on two words | closed | `455e727` | `SourceRuleTest` |
| T4-023 · low · the write-boundary sweep missed three commands | closed | `aacc9b7` | `CommandSweepRuleTest` |
| T4-022 · low · a paragraph glued to a list item | closed | `455e727` | `RepositoryContractTest::test_в_документах_нет_абзаца_приклеенного_к_пункту_списка` |
| T4-024 · low · the scenario count as a band | closed | `455e727` | `RepositoryContractTest::test_число_сценариев_в_документах_равно_настоящему` |
| T4-025 · low · the fix report names a guard that does not exist | closed | `4ab7c1e` | — (a document; see below) |

All guards live in `tests/test_review.py`.

---

## T4-019 · the sign-off gate refused honest work, and accepted a foreign sign-off

**Probe before the fix.** Three throwaway repositories, the gate run end to end:

```
=== honest sign-off from GitHub's private address (+ in the local part) ===
$ .github/dco.sh HEAD~1..HEAD
50819fa plus addressed — no `Signed-off-by: … <12345678+octocat@users.noreply.github.com>`
…
  git rebase --signoff HEAD~1
exit=1

=== sign-off naming a DIFFERENT address, matched through . ===
$ .github/dco.sh HEAD~1..HEAD          # author a.b@example.com, sign-off aXb@example.com
all commits in HEAD~1..HEAD are signed off
exit=0
```

Both directions of the same defect: the author's address went into
`grep -qiE "…<${author}>…"` unescaped, `+` is a quantifier and `.` is a wildcard. The refusal
named `git rebase --signoff`, which regenerates the identical line — a refusal with no way out
of it.

**What was done.** `signoff_addresses()` extracts the address from each well-formed
`Signed-off-by:` line (`sed`, the message folded to lower case) and the caller compares it with
the author's address as a STRING — `grep -qxF`. The address is interpolated into no pattern.

**After the fix**, same probes: the `+` address passes (`exit=0`), the look-alike `aXb` is
refused (`exit=1`).

**Test that catches it.** `DcoGateTest::test_подпись_с_адреса_с_метасимволами_проходит` (three
real-world forms: GitHub's private address, `first.last@company.com`, plus-addressing) and
`DcoGateTest::test_подпись_на_похожий_адрес_не_засчитывается`.

**Reverted fix.** `git show HEAD:.github/dco.sh` (the round-1 script) put back through the
`FINETOOTH_SHELL_GATE` substitution, `bash -n` on it first:

```
bash -n: 0                    ← the reverted script is a valid script: the red is the test's
test_подпись_с_адреса_с_метасимволами_проходит      FAIL  (1 != 0: two commits reported unsigned)
test_подпись_на_похожий_адрес_не_засчитывается      FAIL  (0 != 1: the foreign sign-off passed)
test_нерешаемый_диапазон_роняет_ворота_и_называет_починку  FAIL
Ran 9 tests … FAILED (failures=3)
```

**The other side — what the fix must still allow.** `test_подписанные_коммиты_проходят` (several
authors in one branch, an address typed in another case — the case folding is still there),
`test_коммит_слияния_подписи_не_требует`, and the new
`test_диапазон_без_коммитов_ворота_не_роняет`. All five green on the old and the new script.

**Every address of the class (rule 10).** `grep` over the kit for a value interpolated into a
pattern language: every dynamic regex in `review.py` already goes through `re.escape`
(`rf"…{re.escape(...)}…"`, five sites, none without it); `axes.py` builds no pattern from a
value; in `guard-grep.sh` the pattern and the exclusion are the caller's own extended regexes
by documented design, the marker is matched with `index()` (a fixed string) and `--skip` is a
`find` glob by design. `dco.sh` was the only place, and it is fixed.

---

## T4-026 · the gate announced "all commits are signed off" having examined none

**Probe before the fix.** A fresh repository with an unsigned commit and no `origin/dev`,
running the command CONTRIBUTING documents:

```
$ .github/dco.sh origin/dev..HEAD
all commits in origin/dev..HEAD are signed off
fatal: ambiguous argument 'origin/dev..HEAD': unknown revision or path not in the working tree.
exit=0
```

`git rev-list` was read through a process substitution, where `set -euo pipefail` never sees
its exit code: the loop read nothing, `failed` stayed 0, the script fell through to its success
line. The control range (`HEAD~1..HEAD`) refused correctly, so the gate was green exactly where
git had failed.

**What was done.** The commits are listed before the loop (`if ! commits="$(git rev-list …)"`),
a failure of the listing is a refusal, and the loop reads them from a here-document — which,
unlike a pipe, keeps the counter in the current shell. The refusal names the fix:

```
git cannot list the commits of `origin/dev..HEAD` (its own message is above), so nothing was checked.
Fetch the branch the range starts from and run it again:
  git fetch origin dev
  .github/dco.sh origin/dev..HEAD
If your remote is not called `origin`, name yours: `.github/dco.sh upstream/dev..HEAD`.
```

**Test that catches it.** `DcoGateTest::test_нерешаемый_диапазон_роняет_ворота_и_называет_починку`
— exit 1, nothing about "signed off" on stdout, and `git fetch` named in the refusal.

**Reverted fix.** Red, in the table under T4-019; the reverted script parses (`bash -n` → 0).

**The other side.** A range that resolves to no commits is not a violation:
`test_диапазон_без_коммитов_ворота_не_роняет` (`HEAD..HEAD` → exit 0). Without it, "check the
listing" is one sloppy line away from turning an up-to-date branch into a refusal.

**The class, closed by a guard.** The root is *a gate that cannot go red* — its seventh
instance, and its recorded guard (`GateRegistryTest`) walks `problems.append` inside `cmd_check`
and cannot see a gate written as a shell script at all. Two of the kit's gates are scripts.
`ShellGateMutationTest` turns each `exit N` of each shell gate into `exit 0` in a copy
substituted through the environment (`FINETOOTH_SHELL_GATE`, the shape `FINETOOTH_TOOL` already
has) and requires the suite named beside that script to go red. Measured, all six refusals of
the two scripts:

```
.github/dco.sh refusals: [51, 84]
  clean copy: 0 (OK)
  51: code=1  Ran 9 tests … FAILED (failures=1)
  84: code=1  Ran 9 tests … FAILED (failures=3)
skills/finetooth/assets/guard-grep.sh refusals: [49, 55, 59, 76]
  clean copy: 0 (OK)
  49: code=1  Ran 7 tests … FAILED (failures=1)
  55: code=1  Ran 7 tests … FAILED (failures=1)
  59: code=1  Ran 7 tests … FAILED (failures=1)
  76: code=1  Ran 7 tests … FAILED (failures=1)
```

Three of those four `guard-grep.sh` refusals had no test at all before this round — see
"Incidental fixes". The refusal is found by shape (`exit` with a non-zero code, on its own or
after a semicolon), so a gate written tomorrow falls under the rule by itself; both directions
of that recognition are fed invented scripts in `test_узда_видит_отказ_которого_ещё_нет`.

---

## T4-021 · "every declared gate is run by CI" was two words anywhere in the workflow

**Probe before the fix.** The guard's own logic, applied to the repository's real workflow with
one thing deleted at a time:

```
commands CONTRIBUTING declares: ['python3 -m unittest discover -s tests',
                                 'skills-ref validate skills/finetooth',
                                 '.github/dco.sh origin/dev..HEAD']

=== the `Run the tests` step deleted ===
  old guard (two anchors anywhere): GREEN
=== the whole `unittest` job deleted ===
  old guard (two anchors anywhere): GREEN
```

For the suite the anchors were `python3` — which occurs in the step that installs the skill
validator — and `tests`, which is the workflow's own first line (`name: tests`). Neither anchor
has anything to do with the suite being run, and branch protection keeps requiring a green
`tests` workflow.

**What was done.** `_workflow_steps()` extracts the body of every `run:` (inline and block
scalar); `_runs_command()` decides whether a step runs a documented command: the same program
by NAME (the validator lives in a venv under `$RUNNER_TEMP`), every argument of the documented
command present and in order, a wider step allowed (`-v`), and an argument containing `..`
matched by shape, because CI takes the commit range from the event payload.

**Test that catches it.** `RepositoryContractTest::test_каждые_объявленные_ворота_гоняет_ci`. On
the same two mutations of the real workflow, written to disk and restored byte for byte
afterwards (`git status --porcelain` empty):

```
=== the `Run the tests` step deleted ===
  new guard: RED (exit 1)  Lists differ: ['python3 -m unittest discover -s tests'] != []
=== the whole `unittest` job deleted ===
  new guard: RED (exit 1)  Lists differ: ['python3 -m unittest discover -s tests'] != []
```

**The other side — what must still pass.** A step is allowed to spell the command its own way,
and all three documented commands are spelled differently in CI than in CONTRIBUTING.
`test_узда_видит_ворота_которых_ci_не_гоняет` feeds an invented workflow in which the validator
comes from a venv path, the range comes from `${{ github.event… }}` and the suite carries an
extra `-v`, and requires all three to count — then deletes one step and one command's program
and requires exactly that command to be reported. Without this half, "match the step properly"
would be one strict line away from a guard that refuses the repository's own honest workflow.

**The class.** Root *class guard keyed on incidental syntax* (fifth instance; the guard recorded
for it by block T3 is `SourceRuleTest`). Its meta-rule — every rule over a source must live in
a function and be fed an INVENTED sample, both directions — covered rules over `review.py` and
over the suite, and not rules over a document, which is what a workflow is. `SOURCE_MARKS` now
counts a file read from the repository (`KIT / …`) as such a subject, and
`test_узда_видит_правило_которое_никто_не_кормил` gets a shape for it. Nothing in the suite is
flagged by the widening (measured: `([], [])` before and after), because the new rules of this
round already carry invented samples — which is the point: the next one has to as well.

---

## T4-023 · the write-boundary sweep never reached three of the commands that write

**Probe before the fix.** The rule written for this class, fed the suite as it stood at HEAD:

```
=== a command sweep that never checks the command started ===
  at HEAD : ['test_ни_одна_команда_не_пишет_вне_каталога_ревью']
  now     : []
```

The sweep called every subcommand with `()` and with `("H1",)`; `set-status`, `set-finding` and
`log` are refused by argparse before their own code runs, so three of the commands that WRITE
were outside the write-boundary rule — the rule SECURITY.md's promise rests on.

**What was done.** One table, `BODY_ARGV`, of the arguments at which each command reaches its
body (it existed already, inside `HandWrittenInputTest`; it is now module-level and both sweeps
take it), and `argparse_refused()` — one place that decides what an argparse refusal looks
like. The boundary sweep asserts, per command, that the command started; the table's coverage
of the tool's command list is asserted too, so a new command cannot be added without arguments
at which it runs.

**Test that catches it.** `WriteBoundaryTest::test_ни_одна_команда_не_пишет_вне_каталога_ревью`,
with the mutation that puts the round-1 shape back (no arguments for every command):

```
FAIL … (cmd='set-status', args=())  'the following arguments are required' is not false
FAIL … (cmd='set-finding', args=()) 'the following arguments are required' is not false
FAIL … (cmd='prompt', args=())      …    (and import, hypotheses, restamp, log)
exit: 1
```

Run on a copy of the suite in a throwaway directory of the repository, removed afterwards.

**The other side.** The three commands must still be ABLE to write — inside `docs/review/`. The
same sweep now runs them for real (`set-status H1 running`, `set-finding H1-001 open`,
`log H1 строка`) and requires the tree outside `docs/review/` to be untouched, while
`test_итог_пишется_туда_куда_сказали_и_только_туда` keeps the one documented exception
(`summary`, and `summary --out` even outside the repository) working. `summary` is deliberately
swept without `--out`: the default path is the promise under test, the flag is the user's
request and has its own test.

**The class, closed by a rule.** Root *guard enumerates its subject without exercising it*
(fourth instance). `CommandSweepRuleTest` reads the suite's own source and reports a test that
takes the command list from the tool (`--help`, or the shared `_subcommands`) and runs commands
from a variable without ever consulting the argparse vocabulary — by shape, so the sweep nobody
has written yet is covered. Fed the suite at HEAD it names exactly the defective sweep (above);
both directions are fed invented sweeps, including one that asks through the shared helper and
one that carries its own copy of the vocabulary — the honest form that must not be flagged.

---

## T4-024 · the public scenario count was a band, not a measurement

**Probe before the fix.** The documents said 325 (all five places, corrected by block T3's
round); the guard permitted anything from nine tenths of the real count up to it, so the round
that introduced the band shipped 270 against a suite of 296. And the measurement itself:

```
$ python3 -m unittest discover -s tests -k test_число_сценариев   # the guard alone
AssertionError: 325 != 1 : AGENTS.md называет 325 сценариев, а их 1
```

`unittest.defaultTestLoader` carries the patterns of `-k` inside it, so under a filter the
"real count" collapsed to the number of tests the filter let through — a figure that depends on
how the suite was invoked is not a measurement, and it is the one the public number is compared
with.

**What was done.** `scenario_count()` measures with its own loader; the assertion is exact
equality; the refusal names the command to run and the three files to change. README (both
languages) and AGENTS.md now say 341, measured.

**Tests that catch it.** `test_число_сценариев_в_документах_равно_настоящему` (red on any
document left behind: measured at 325 against 341 while this round's tests were being written)
and `test_замер_числа_сценариев_не_зависит_от_способа_запуска`, which sets a pattern on the
shared loader and requires the count not to move — red on the old measurement, green on the new.

**The other side.** The guard must not forbid a legitimate state: it reads the count from the
suite itself, so the documents can be brought back into line by one measurement, and the
message says exactly how. The runtime beside the count stays prose: it depends on the machine,
and the documents say so.

**Cost of the decision, stated plainly.** Exact equality means a commit that adds a test and
does not update the three documents is red. That is the point (AGENTS.md rule 4 — numbers are
measurements), and it is why the refusal carries the command and the file list. The intermediate
commits of this round carry the interim number for the same reason; the tip is measured.

---

## T4-022 · a paragraph glued to a list item, in both CHANGELOGs

**Probe before the fix.** The rule, fed the two files as they stood at HEAD:

```
CHANGELOG.md at HEAD    : ['77: Block T2 of the same review — the role templates in both …']
CHANGELOG.ru.md at HEAD : ['77: Блок T2 того же ревью — шаблоны ролей на обоих языках, образцы …']
CHANGELOG.md now        : []
CHANGELOG.ru.md now     : []
```

By markdown's lazy continuation the paragraph that introduces block T2 was part of the last
bullet of block T4 — an entry about anonymisation — and the fifteen bullets below it arrived
under no heading. RELEASING gate 4 takes the release notes from this section verbatim.

**What was done.** A blank line in both files, and a rule over every document in the root
(`git ls-files ':(glob)*.md'`, so a new document falls under it): no paragraph may start on the
line after a list item. Fences are skipped.

**Test that catches it.** `test_в_документах_нет_абзаца_приклеенного_к_пункту_списка`. Measured
against all twelve root documents: the rule reports the defect and nothing else (nine documents
checked by hand at the time of writing, then all twelve by the test).

**The other side.** An indented continuation, a nested list item, the next bullet, a heading, a
compare-link reference and a list inside a fence are all legitimate and must not be reported:
`test_узда_видит_абзац_приклеенный_к_пункту` feeds each one. Without that half the rule would
refuse the CHANGELOG's own link references, of which there are dozens.

---

## T4-020 · the register recorded two classes as closed by guards that do not close them

**Probe before the fix.** `review roots T4` on the current register, and the measurement behind
it:

```
   3 × a rule declared enforced with nothing enforcing it
         — guard: …::test_версии_python_из_шапки_скилла_прогоняются_в_ci
       T4-009  RELEASING.md:23   T4-010  CONTRIBUTING.md:75   T4-017  SKILL.md:5
   4 × a number in a public document not checked against its source
         — guard: …::test_пороги_из_документов_читаются_из_кода
       T4-004  README.md:281   T4-005   T4-006   T4-024
```

With the whole `dco` job deleted from the workflow — T4-010's defect restored exactly — the
test the register names as that class's guard is green; with the README left at the old
scenario count, the test the register names for the numbers class is green too. Measured (the
workflow written, the test run, the file restored byte for byte):

```
=== the `dco` job deleted from .github/workflows/tests.yml ===
  test_версии_python_из_шапки_скилла_прогоняются_в_ci  GREEN
  test_каждые_объявленные_ворота_гоняет_ci             RED
=== README.md left at the old scenario count ===
  test_пороги_из_документов_читаются_из_кода           GREEN
  test_число_сценариев_в_документах_равно_настоящему   RED
```

So each class could be reopened with its recorded guard green, and `check` said nothing because
a `rule` string was present. The tool stores and validates a rule PER FINDING (it checks that
every distinct rule of a root names an existing file); `roots` prints the first one it finds,
which is what made one guard look like the whole root's.

**What was done.** Each finding's `rule` is now the guard that fires on that finding:

| finding | rule recorded |
|---|---|
| T4-004, T4-024 | `…::RepositoryContractTest::test_число_сценариев_в_документах_равно_настоящему` |
| T4-005, T4-006 | `…::RepositoryContractTest::test_пороги_из_документов_читаются_из_кода` |
| T4-009, T4-010 | `…::RepositoryContractTest::test_каждые_объявленные_ворота_гоняет_ci` |
| T4-017 | `…::RepositoryContractTest::test_версии_python_из_шапки_скилла_прогоняются_в_ci` |

and the fix report of round 1 says so where it claimed otherwise. Both roots keep a guard for
every instance, and every recorded guard goes red on its own instance — measured above, and
once more for T4-017 in round 1's own table.

**Test that catches it.** None, and deliberately: the defect is a wrong value in the review's
own register, not in the kit. What the kit could hold — that a root's recorded guard actually
fires on each of its instances — is `GateMutationTest`'s idea applied to the register, and it
needs the tool to know which test belongs to which finding rather than to a root. That is a
change to `review.py`, in block T1, which is closed: it is written up under "found, not fixed".

---

## T4-025 · the round-1 fix report named a guard that does not exist

**Probe before the fix.** `grep` for the name the report gives as T4-004's guard:

```
docs/review/reports/T4-repo-contract.fix.md:16   test_число_сценариев_в_документах_равно_настоящему
tests/test_review.py (HEAD)                      test_число_сценариев_в_документах_не_больше_настоящего
```

The name in the report resolved to nothing on `HEAD`: commit `2f29968`, inside the same range,
renamed the test and changed what it asserts. The report also stated `Ran 270 tests … OK`,
which was the fixer's worktree, not the merged tree (296).

**What was done.** Three notes in the report, each where the stale figure stands: under T4-004
(what the numbers were, why they drifted, and that the name and the exact equality came back in
round 2), under "What was run" (the merged tree ran 296), and in the classes table (whose rules
were corrected — T4-020). The report's account of the round is left as it was: it is the record
of that round, and a note is honest where a silent edit is not.

**Test that catches it.** None: a report of a past round is prose about a moment. What is
mechanically held is the thing the report was wrong about — the guard's name and its assertion
are now what the register and the report both say.

---

## Incidental fixes (rule 4: the class, not the instance)

1. **Three refusals of `guard-grep.sh` had no test.** Found while closing T4-026's class: the
   mutation guard demands a red for every shell refusal, and these three stayed green. An
   unknown argument, no `--pattern`/`--marker`, and no paths — all three are what a Makefile
   reaches by a typo, and all three are the difference between "scanned nothing" and "the tree
   is clean", the distinction the script exists for. Tests:
   `GuardGrepTest::test_неизвестный_ключ_это_отказ_а_не_тишина`,
   `…::test_без_образца_и_маркера_это_отказ_а_не_тишина`, `…::test_без_путей_это_отказ_а_не_тишина`.
   Each red on its own refusal turned into `exit 0` (measured, table under T4-026); the allowed
   side — a correct invocation over a clean tree is silence and exit 0 — is the existing
   `test_каждому_вызову_свой_маркер_и_дерево_чистое`.
2. **The scenario count was measured with the loader that carries `-k`.** Written up under
   T4-024 because it is the same finding's mechanism; its own test is
   `test_замер_числа_сценариев_не_зависит_от_способа_запуска`.
3. **One vocabulary for argparse refusals.** `BODY_ARGV` and `ARGPARSE_REFUSED` moved out of
   `HandWrittenInputTest` to module level with `argparse_refused()`, so the two sweeps cannot
   disagree about what "the command did not start" looks like. Held by `CommandSweepRuleTest`,
   which requires a sweep to consult that vocabulary.

## Found, not fixed

**The tool cannot check that a root's guard fires on each instance** (`review.py`,
`cmd_check`, the root-rule gate at the `ROOT_RULE_AT` threshold). It requires a rule to exist
and the path to resolve; nothing ties a rule to the finding it closes, and `roots` prints one
rule for a whole root, which is how T4-020's wrong bookkeeping looked right for a round. The
shape of the fix is known — the register already stores a rule per finding, so `roots` could
print them per instance and `check` could refuse a root where some instance has no rule at all.
Block T1 is closed; this is the lead's call.

**Two roots of the register describe one class under two names.** *A value interpolated into a
pattern language unescaped* (T4-019, this round) and *a name handed to git as a pathspec*
(T1's, closed by `SourceRuleTest::test_имя_файла_не_уходит_к_git_образцом`) are the same defect
with two pattern languages. Merged, the class has three instances and a guard already; kept
apart, each stays under the threshold. Roots are written by the hunter and the verifier, and
merging two of them is not a fixer's decision.

**Nothing else.** The runtime figures still hold after this round's twenty-three new tests
(`Ran 341 tests in 330.661s` — README and AGENTS.md say about six minutes, CONTRIBUTING about
five, and the measurement sits between them), and `grep` found no second address for T4-019's
class (above).

## Observations outside the assignment

- **A neighbouring worktree's suite runs on the same machine.** The T3 round-2 fixer's run
  overlapped part of mine — separate trees, so no contamination of state, but it costs wall
  clock: the same suite measured 413s with its run beside mine and 330s alone. Round 1's
  reviewer reported the sharper version of this (two revert-mutating reviewers in ONE worktree
  contaminating each other). Every mutation measurement in this report was taken with this tree
  otherwise idle, and every file written during a measurement was restored and verified with
  `git status --porcelain`.
- **An exact scenario count and a suite that grows are in tension by design.** The band was a
  reasonable answer to a real annoyance, and removing it puts the annoyance back. The reason it
  has to go is that the number is the README's evidence for "tests proven by mutation": evidence
  that may be a tenth wrong is not evidence. If the annoyance bites, the answer is a make
  target that re-measures and rewrites the three places, not a wider band.

## Rejected and deferred findings

None. All eight findings reproduced on the current code.

## What was run

**The suite**, from the repository root, with the tree otherwise idle:

```
$ python3 -m unittest discover -s tests
.........................................................................…
----------------------------------------------------------------------
Ran 341 tests in 330.661s

OK
```

Twenty-three of those 341 are this round's. The relevant suites were also run on their own
after each fix (`DcoGateTest`, `GuardGrepTest`, `ShellGateMutationTest`, `CommandSweepRuleTest`,
`WriteBoundaryTest`, `HandWrittenInputTest`, `SourceRuleTest`, `RepositoryContractTest`).

**The skill format.** `skills-ref` is not installed on this machine and installing it is
refused by this environment (the same limit as in round 1). This round changes nothing under
`skills/finetooth/` — `git diff d33527c..HEAD -- skills/` is empty — so the validator's verdict
cannot have moved; the last run of it is round 1's, over the same bytes.

**The sign-off gate over this round's own commits** — the gate that was fixed, run on the work
that fixed it:

```
$ .github/dco.sh d33527c..HEAD
all commits in d33527c..HEAD are signed off
exit: 0
```

**The state check**: `STATECHECK`
