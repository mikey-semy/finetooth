# T4 — fix review, round 1

## What was checked and how

The diff was read in full — 464 KB, 4091 lines, range `f1a44a0..HEAD`. It fits in one
context; no `--scope` split was taken, and every statement below is about the whole range.

Note on the range: it carries **two** blocks' fixes, T4 (`9c66593`, `fe08bbd`, `002dbf1`,
`25a5421`, `02543ab`, `deea162`…) and T2 (merged at `82ade22`), plus the lead's follow-up
`2f29968`. T4 is the assignment; the T2 commits were read for interference, and one finding
below (R1-004) lands in a T4-owned file because of the T2 merge.

**Proved by reverting** (each mutation applied to the working tree, the named tests run, the
file restored byte for byte, `git status` checked after):

| mutation | test | verdict |
|---|---|---|
| `review_id` guard removed from `check_definition` | `HandWrittenInputTest::test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении` | **RED** ✓ (`KeyError: 'review_id'`, exit 1 — the original T4-016 defect returns; the reverted tool compiles and runs) |
| `paths`-as-a-string guard removed | same | **RED** ✓ |
| a write site pointed outside `docs/review/` | `WriteBoundaryTest::test_ни_одна_команда_не_пишет_вне_каталога_ревью` | **RED** ✓ (and `test_итог_пишется_туда_куда_сказали_и_только_туда` red too — the allowed side is genuinely pinned) |
| the old `SECURITY.md` promise restored | `WriteBoundaryTest::test_обещание_безопасности_называет_то_же_исключение` | **RED** ✓ |
| old licence sentence back in `SKILL.md` | `SkillFormatTest::test_поле_лицензии_это_её_обозначение_и_ничего_сверх` | **RED** ✓ |
| `COUPLING_HUB_SHARE` → 0.25, documents untouched | `RepositoryContractTest::test_пороги_из_документов_читаются_из_кода` | **RED** ✓ |
| README left at the old scenario count | `…::test_число_сценариев_в_документах_не_больше_настоящего` | **RED** ✓ |
| `actions/checkout@v5` restored | `…::test_действия_ci_закреплены_коммитом` | **RED** ✓ |
| a compare link removed from `CHANGELOG.md` | `…::test_у_каждой_версии_в_истории_есть_ссылка_на_сравнение` | **RED** ✓ |
| the code-of-conduct cross-link removed | `…::test_у_двуязычных_файлов_ссылка_друг_на_друга_в_первой_строке` | **RED** ✓ |
| `RELEASING.md` sent back to `scripts/review.py` | `…::test_живое_руководство_ведёт_на_существующие_пути` | **RED** ✓ |
| a Python version dropped from the matrix | `…::test_версии_python_из_шапки_скилла_прогоняются_в_ci` | **RED** ✓ |
| the `dco` job removed from CI | `…::test_каждые_объявленные_ворота_гоняет_ci` | **RED** ✓ |
| the `skills-ref validate` step replaced by `true` | same | **RED** ✓ |

Every fix in the block therefore has a test that is red without it. The failures below are
not about fixes that do not work; they are about **guards that are recorded as covering more
than they cover**, and about one new gate that refuses honest work.

**Gates checked by violation** (rule 7), beyond the table above:

- the `dco` job removed → the guard the register names for that class stayed **green**
  (R1-002);
- the step that actually runs the suite deleted from CI, and then the whole `unittest` job
  deleted → `test_каждые_объявленные_ворота_гоняет_ci` stayed **green** both times (R1-003);
- `.github/dco.sh` run against real repositories and its grep run directly against
  real-world address forms (R1-001);
- `.github/dco.sh` run on an unresolvable range and on the exact command CONTRIBUTING
  documents, in a clone lacking `origin/dev`, with an unsigned commit present (R1-008).

**Reproduced live:** `.github/dco.sh` was run end to end in throwaway git repositories —
signed and unsigned commits, several authors, a merge commit, an unresolvable range — and
its matching was exercised against actual `Signed-off-by:` lines; `init` was run over
damaged `blocks.json` definitions, with and without the fix; the `WriteBoundaryTest` call
pattern was replayed against all 23 subcommands to see which bodies it reaches.

**The suite on the merged tree**, run clean, nothing else touching the working tree:

```
Ran 296 tests in 300.638s

OK
```

Green. (296, not the 270 both fix reports state and the documents claim — see R1-006.)
`review refs` says no finding of the register is named outside `docs/review/`; `review check`
is red only on the staleness the fixer disclosed for the lead (fingerprints and
`code_sha` drift on T1/T3 findings whose files this round re-numbered), plus the two T3 root
classes that are correctly still open.

**Not done, and why:**

- A second fix reviewer (block T2) is working in this same working tree and revert-mutating
  `SKILL.md` and `skills/finetooth/scripts/review.py` at the same time. My first full suite
  run was corrupted by exactly that — a `SyntaxError` from a file caught mid-write, surfacing
  as a failing test — and one mutation came back a **false green** for the same reason. Both
  were re-run serially with the tree clean; the green suite and every entry in the table
  above are from those clean runs. The lead should know that **two revert-mutating reviewers
  in one worktree contaminate each other**: had I not re-run, I would have reported a red
  suite and a guard that does not hold, both wrongly. This is a process problem, not a
  finding against the fixer.
- Python 3.12 was not exercised: only 3.14 exists on this machine. The matrix cell is real
  in CI and unverifiable here.
- `skills-ref validate` was not run (not installed; the fixer documented the same limit).

## Findings

### R1-001 · medium · The new DCO gate refuses a correctly signed-off commit when the author's email contains a regex metacharacter, and the remedy it names cannot fix it

**Location:** `.github/dco.sh:25`

**What is wrong:** the commit's author address is interpolated straight into an extended
regular expression:

```sh
grep -qiE "^[[:space:]]*Signed-off-by:[[:space:]]+.+<${author}>[[:space:]]*$"
```

`${author}` is never escaped, so every regex metacharacter in an email address changes the
meaning of the pattern. It fails in both directions.

**Failure scenario (refusing honest work — the direction that matters most):** GitHub's
privacy-protected commit address, which is the default for every account with “Keep my email
addresses private” switched on and the address GitHub's own web UI commits under, has the
form `12345678+octocat@users.noreply.github.com`. Measured directly:

```
Signed-off-by: The Octocat <12345678+octocat@users.noreply.github.com>
pattern ...<12345678+octocat@users.noreply.github.com>...   →  NO MATCH
```

`+` is a quantifier, so `12345678+octocat` requires `1234567` followed by one-or-more `8`
followed by `octocat` — which the literal text does not contain. Every commit from such a
contributor is rejected as unsigned. The refusal then prints

```
git rebase --signoff <base>
```

which regenerates the *identical* `Signed-off-by:` line and therefore cannot clear the gate:
the contributor is in a loop with no way out of it. Plain plus-addressing
(`dev+finetooth@example.com`) fails the same way; `.`, `*`, `?`, `|`, `{`, `}`, `^`, `$` are
all legal in a local part and all metacharacters here.

**Failure scenario (accepting what it exists to reject):** `.` is a wildcard, so for an
author `a.b@example.com` a sign-off naming the *different* address `aXb@example.com`
matches — verified:

```
Signed-off-by: Somebody Else <aXb@example.com>   vs author a.b@example.com  →  MATCHED
```

That is precisely what `test_подпись_с_чужой_почтой_не_засчитывается` was written to
forbid, and dots in local parts (`first.last@company.com`) are the common form.

**Why it is a defect:** invariant 3 — a refusal must name the command that fixes it, and
this one names a command that does not. Invariant 1 applied to a gate the repository now
requires on every pull request: it is simultaneously satisfiable on a wrong state and
unsatisfiable on a right one. Rule 3 of the fix-review contract is the sharper point: the
“forbidden no longer passes” tests exist (`test_подпись_с_чужой_почтой_не_засчитывается`),
but the “allowed still passes” test (`test_подписанные_коммиты_проходят`) covers only plain
addresses and a case difference — the one direction whose breakage is noticed by the person
whose work disappeared is the one not covered.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** a value interpolated into a pattern language unescaped

*(Same class as the `[handle]`-read-as-a-character-class defect the invariants already
record. The fix is a literal comparison — parse the address out of the line and compare
strings, or `grep -F` on the assembled `<addr>` — not a longer regex.)*

### R1-002 · medium · The register records both T4 defect classes as closed by a guard that cannot fire on two thirds of their instances

**Location:** `docs/review/findings.jsonl` — the `rule` field of T4-009, T4-010, T4-017 (and
of T4-004)

**What is wrong:** `review roots T4` now prints

```
3 × a rule declared enforced with nothing enforcing it
      — guard: tests/test_review.py::RepositoryContractTest::test_версии_python_из_шапки_скилла_прогоняются_в_ci
    T4-009  RELEASING.md:23      (the release gates called "all mechanical")
    T4-010  CONTRIBUTING.md:75   (the DCO)
    T4-017  SKILL.md:5           (the Python versions)
```

That test compares `SKILL.md`'s `compatibility:` line with the CI matrix. It is the guard for
T4-017 and for nothing else. The fixer's own report names
`test_каждые_объявленные_ворота_гоняет_ci` as this class's rule; the register says otherwise,
and the register is what outlives the conversation.

**Failure scenario:** measured. With the whole `dco` job deleted from
`.github/workflows/tests.yml` — T4-010's defect restored exactly — the recorded guard runs
**green**:

```
test_версии_python_из_шапки_скилла_прогоняются_в_ci   GREEN
test_каждые_объявленные_ворота_гоняет_ci              RED   (команда='.github/dco.sh …')
```

So the class the review records as closed by a guard can be reopened with that guard green,
and `check` says nothing because a `rule` string is present. The second root has the same
shape: T4-004 (the scenario count) carries
`rule: …test_пороги_из_документов_читаются_из_кода`, and with the README left at the old
count that test is green while `test_число_сценариев_в_документах_не_больше_настоящего` is
red — again the recorded guard is not the one that fires.

**Why it is a defect:** invariant 2 — a guard that can be holed while the suite stays green
is not a guard, and here it is worse: the register asserts coverage that does not exist.
This is T3-003's class (“a gate registered against any existing test name satisfies the
guard with zero coverage”) realised in the review's own live data.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** a class recorded as closed by a guard that does not close it

### R1-003 · medium · The new class guard does not fire when CI stops running the test suite — the first gate CONTRIBUTING names

**Location:** `tests/test_review.py:4419`
(`RepositoryContractTest::test_каждые_объявленные_ворота_гоняет_ci`)

**What is wrong:** the guard reads the commands out of CONTRIBUTING's `sh` blocks and
requires, per command, that two *anchors* appear anywhere in the concatenated workflow text:
`Path(tokens[0]).name` and the last token. For

```sh
python3 -m unittest discover -s tests
```

the anchors are `python3` and `tests` — and `python3` occurs in the `skill` job
(`python3 -m venv …`) while `tests` occurs in the workflow's own first line, `name: tests`.
Neither anchor has anything to do with the suite being run.

**Failure scenario:** measured by violation.

| violation introduced | guard |
|---|---|
| the `Run the tests` step deleted from the `unittest` job | **GREEN** |
| the whole `unittest` job deleted | **GREEN** |
| the `skills-ref validate` step replaced by `true` (control) | RED |

CI can therefore stop running the suite entirely and the rule whose stated job is “every
command CONTRIBUTING tells a contributor to run must be run by a workflow” stays green —
while branch protection keeps reporting a green `tests` workflow before a merge into
`master`.

**Why it is a defect:** invariant 1 and 2, and SECURITY.md's own wording: a check that goes
green on a state that is wrong is the most serious class here. It is also the load-bearing
half of the pair in R1-002 — the guard the fixer *intended* for that class does not cover
its most important instance either.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** class guard keyed on incidental syntax

*(Existing root, already carrying T3-002, T3-012 and T3-014 — `check` is already red with
“3 instances … and no guard” for it, so this is the **fourth** instance and the class is
overdue a rule rather than a fourth fix.)*

### R1-008 · medium · `.github/dco.sh` reports "all commits are signed off" and exits 0 whenever git cannot resolve the range — including the invocation CONTRIBUTING documents

**Location:** `.github/dco.sh:31` (`done < <(git rev-list --no-merges "$RANGE")`)

**What is wrong:** `git rev-list` runs inside a process substitution. `set -euo pipefail`
does not see its exit status, so when git fails the `while` loop simply reads nothing,
`failed` stays 0, and the script falls through to its success line. The gate announces that
it checked and found everything signed, having examined no commits at all.

**Failure scenario:** reproduced live, end to end. A fresh clone with an unsigned commit on
the branch and no `origin/dev` reference — a contributor who cloned only the default branch,
or whose remote is named `upstream` — running the command CONTRIBUTING gives them verbatim:

```
$ .github/dco.sh origin/dev..HEAD
fatal: ambiguous argument 'origin/dev..HEAD': unknown revision or path not in the working tree
all commits in origin/dev..HEAD are signed off
$ echo $?
0
```

The control, with a range that resolves, refuses correctly:

```
$ .github/dco.sh HEAD~1..HEAD
7a9d8b0 unsigned contribution — no `Signed-off-by: … <contrib@example.com>`
$ echo $?
1
```

`does-not-exist..HEAD` and any other unresolvable range behave identically. git's `fatal:`
goes to stderr, where a contributor scanning for the verdict does not look — the last line
says the check passed.

**Why it is a defect:** invariant 1, and SECURITY.md's own ranking — a check that goes green
on a state that is wrong is the most serious class the kit recognises. The kit has been here
before: T1-011 was `stale_tree` silently inert when `refs/remotes/origin/HEAD` was absent,
i.e. the identical failure (a gate quietly disabled by a missing remote) in the identical
place (a checkout with no remote or a remote not named `origin`). In CI the configured range
comes from the event payload with `fetch-depth: 0` and normally resolves, so the sharp edge
is the documented local run — which is the one CONTRIBUTING added in this very round so the
gate would not "run for the first time on someone else's pull request".

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** a gate that cannot go red

*(Existing root, already carrying six instances and recorded as closed by
`GateRegistryTest` — which walks `problems.append` inside `cmd_check` and therefore cannot
see a shell gate at all. Another instance of the theme in R1-002: the recorded guard does not
reach this address.)*

### R1-004 · low · The T2 section's opening paragraph is swallowed into a T4 bullet in both CHANGELOGs

**Location:** `CHANGELOG.md:76-78`, `CHANGELOG.ru.md:76-78`

**What is wrong:** the paragraph that introduces the T2 block follows the last T4 bullet with
no blank line between them:

```markdown
- **`NOTICE.md` promised an anonymity it does not keep.** … traceable.
Block T2 of the same review — the role templates in both languages, the samples in `assets/`,
`SKILL.md` and the toy example: 15 findings, all closed here.
```

By Markdown lazy continuation that paragraph is part of the `NOTICE.md` list item, not a
paragraph of its own. The equivalent T4 intro three paragraphs above *is* preceded by a blank
line, so the two sections render differently for no reason.

**Failure scenario:** RELEASING gate 4 takes the release notes from this section verbatim. A
reader of the published notes sees the NOTICE.md entry end with “…with the paths a number
needs to be traceable. Block T2 of the same review — … 15 findings, all closed here.”, and
the fifteen T2 bullets below it arrive under no heading at all: the section that says which
block they belong to has been absorbed into an unrelated entry about anonymisation.

**Why it is a defect:** the block's own manifest calls a CHANGELOG entry in the wrong place a
finding, and this is the file whose contents become the public release notes. Identical in
both languages, so it is not a one-language slip.

**Introduced by this round or present before:** introduced by this round (at the T2 merge,
`82ade22`, in a T4-owned file).

**Confidence:** confirmed

**Root:** *(single instance)*

### R1-005 · low · `WriteBoundaryTest` never reaches the body of three of the tool's write commands

**Location:** `tests/test_review.py:3012`
(`WriteBoundaryTest::test_ни_одна_команда_не_пишет_вне_каталога_ревью`)

**What is wrong:** the guard calls each subcommand with `()` and with `("H1",)`. Measured by
reproducing that exact call pattern against all 23 subcommands:

```
body reached (20): init, version, setup, status, next, coverage, prompt, import, hypotheses,
                   restamp, backfill, inventory, sizes, coupling, order, refs, summary,
                   roots, findings, check
NEVER past argparse (3): set-status, set-finding, log
```

The three that never run are `set-status`, `set-finding` and `log` — which is to say, three
of the commands that actually **write**. They are rejected by argparse before `cmd_*` is
entered, so they are not under the write-boundary rule at all.

**Failure scenario:** a future change that makes `log` or `set-finding` write outside
`docs/review/` — the journal or the register redirected, a `--out`-style flag added — passes
the guard the report describes as one “a new command falls under by itself”, and SECURITY.md
keeps promising a boundary nothing checks for those commands.

**Why it is a defect:** this is the *same* blind spot the same commit series diagnosed and
repaired one guard over: T4-016's write-up says in as many words that
`HandWrittenInputTest` was green for as long as it existed because “it called every
subcommand with a block id and a file name, so `init`, which takes neither, never got past
argparse”. `HandWrittenInputTest` now calls each command with and without arguments;
`WriteBoundaryTest`, written in the same series, does not. The fix went to one address of the
pattern and not to the other.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** guard enumerates its subject without exercising it

*(Existing root, already carrying T3-003, T3-005 and T3-015 — `check` is already red with
“3 instances … and no guard” for it, so this is the **fourth** instance.)*

### R1-006 · low · The scenario count in the documents was already 26 behind the suite when the round closed, and the guard was loosened in the same range to permit it

**Location:** `README.md:281`, `README.md:448`, `README.ru.md:258`, `README.ru.md:417`,
`AGENTS.md:68`

**What is wrong:** all five places say **270 scenarios**. Measured on the merged tree:

```
Ran 296 tests in 310.234s
```

The 270 was honest in the T4 fixer's worktree; merging T2 added its 26 tests and nothing
re-measured. The guard does not object because the final commit in this range (`2f29968`)
replaced exact equality with a band — at most the real count, and no less than nine tenths
of it — and 270 ≥ 296 × 9/10 = 266 by four.

**Failure scenario:** the reader AGENTS.md sends to “Check before committing” runs the suite,
sees 296 against a documented 270, and is back in the position T4-004 described — unable to
tell whether the checkout, the command or the document is wrong. The band means the number
may now be wrong by up to a tenth permanently, in the one figure the README offers as public
evidence that the kit's tests are real.

**Why it is a defect:** AGENTS.md rule 4 — numbers are derived from measurement. The
loosening is defensible as a way to stop every test-adding PR going red; what is not
defensible is shipping the round with the number already outside the measurement it names.
Re-measuring the five places costs one edit.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** a number in a public document not checked against its source

*(Existing T4 root — this is its fourth instance, and its recorded guard is the one R1-002
shows to be the wrong one.)*

### R1-007 · low · The fix report names a guard test that does not exist

**Location:** `docs/review/reports/T4-repo-contract.fix.md` — the findings table (T4-004) and
the “Two classes closed by a rule” table

**What is wrong:** both name
`RepositoryContractTest::test_число_сценариев_в_документах_равно_настоящему`. No such test
exists on `HEAD`: `2f29968`, inside this same range, renamed it to
`test_число_сценариев_в_документах_не_больше_настоящего` and changed what it asserts
(equality → a band, see R1-006). The report also states `Ran 270 tests … OK`, which is the
fixer's worktree, not this range's tree (296).

**Failure scenario:** the report is the account a later reader checks the round against.
Looking up the named guard returns nothing, and there is no way from the report to tell
whether the test was dropped, renamed, or never written — the same ambiguity T1-067 was
raised for one round earlier.

**Why it is a defect:** rule 1 of the fix-review contract — a discrepancy between the report
and the diff is a finding in itself. It is small, and it is the one class this review has
already paid for once.

**Introduced by this round or present before:** introduced by this round.

**Confidence:** confirmed

**Root:** *(single instance)*

## Checked and found correct

- **The `SECURITY.md` boundary (T4-003) is now true, and checked by running rather than by
  proof-reading.** `review.py` imports no `urllib`, `socket`, `http`, `ssl` or `requests`,
  and every one of its `subprocess.run` call sites invokes `git` and nothing else — so
  “sends nothing over the network and runs no command but `git`” holds as written. The
  `run-role.sh` exception is described accurately (`$TMPDIR/finetooth-runs`, `claude -p`),
  and `WriteBoundaryTest` pins the promise and the behaviour to each other in both
  directions. The one wrinkle is R1-005, which narrows the sweep, not the promise.
- **T4-016 is genuinely fixed and genuinely widened.** Reverting only the `review_id` check
  brings back `KeyError: 'review_id'`, exit 1, on `init` — the exact defect — and the guard
  goes red; the reverted tool still compiles, so the red is the test doing its job and not a
  build failure. The allowed side (`test_целое_определение_по_прежнему_принимается`: an
  exclusion with extra keys, a block with no `paths`, a definition with no `exclusions`)
  passes on both old and new code, so nothing previously legal was taken away. The damage
  table covering eleven shapes × every command × two argument shapes is a real widening.
- **The licence field (T4-001).** Reading the identifier out of `LICENSE`'s first line rather
  than hardcoding `MIT` is the right shape: the field cannot drift from the file again.
  Mutation red as claimed.
- **The `coupling` thresholds in the documents (T4-005, T4-006).** The guard reads
  `COUPLING_*` out of `review.py` and demands the documents describe them in words; moving
  `COUPLING_HUB_SHARE` to 0.25 turns both READMEs red. The CHANGELOG's *Added* and *Fixed*
  entries now describe one rule instead of two.
- **`actions/checkout` pinning (T4-014).** All four `uses:` lines across both workflows carry
  40-hex commits; `stale.yml`'s existing pin satisfies the same rule, so the guard is not
  written around the one file it was added for.
- **The compare links (T4-008) and the codes of conduct (T4-018).** Both guards walk the
  files rather than a list, both go red on one removal, and `[0.6.0]` correctly compares
  from `v0.5.1` now.
- **`NOTICE.md` (T4-002).** The new wording is the honest one: it scopes the promise to
  someone else's projects and states plainly that the owner's own are named with their
  paths. Not mechanically guarded, and correctly declared as not guarded — a list of
  forbidden names would have to contain the names the promise is about.
- **`README.ru.md` parity (T4-011).** The six guarantees and the Language paragraph are
  present and say the same things as the English. The repetition the fixer flagged (the
  install command appearing twice) mirrors the English file exactly, so it is symmetry, not
  new damage — and prose repetition is not a finding here.
- **The proposal template (T4-007) and `RELEASING.md` (T4-013).** The path rule reads the
  paths out of the documents themselves and goes red on either file restored. Declaring bare
  names (`blocks.json`, `SKILL.md`) out of scope is a reasonable line and is stated.

## Is another round needed

**Yes.** Four medium findings, and they are not cosmetic:

- R1-001 and R1-008 are both defects in the DCO gate this round *introduced*, and they point
  in opposite directions: it turns away correctly signed commits from any contributor using
  GitHub's private email — with a printed remedy that cannot clear it — and it announces
  "all commits are signed off", exit 0, when git could not resolve the range it was given,
  including in the local invocation CONTRIBUTING added in this same round. A gate that both
  refuses honest work and passes unexamined work is worse than the checkbox it replaced,
  because it now reads as enforcement.
- R1-002 and R1-003 together mean the two defect classes this block records as *closed by a
  rule* are not: one is recorded against the wrong test, and the test that was meant for it
  does not fire on its most important instance.

The fixes themselves are sound — every one of the fourteen mutations in the table above went
red without its fix, the allowed sides pass, and the block genuinely got better: the security
promise is now true and executable, `init` no longer tracebacks on a hand-written
definition, the licence statement is correct, and CI is pinned, English and running the
versions the skill claims. What did not hold is the *bookkeeping of closure* — which for this
kit is the product.

**Where the findings sit:** 8 of 8 are inside code this round changed, 0 outside it. For a
first round that is the expected shape and not yet the signal rule 11 warns about — there is
no previous round's fixes to be re-breaking. It becomes the signal if round 2 again puts its
heaviest finding inside round 1's changes. Worth noting for that judgement: five of the eight
(R1-001, R1-002, R1-003, R1-005, R1-008) are about the *new guards and the new gate*, not
about the document fixes — the prose half of this block is in good shape, and the machinery
added to hold it is where the defects are.

**Two of the findings are the fourth instance of classes `check` is already red about.**
`review check` today prints, unprompted:

```
root 'class guard keyed on incidental syntax': 3 instances (T3-002, T3-012, T3-014) and no guard
root 'guard enumerates its subject without exercising it': 3 instances (T3-003, T3-005, T3-015) and no guard
```

R1-003 joins the first and R1-005 the second. Both are T3's roots and T3 is still `fixing`,
so the economical move is to let T3's fixer close each class with one rule rather than have
T4's round 2 fix two more instances by hand. R1-002's bookkeeping error should be corrected
in T4 regardless — it is one `set-finding --rule` call per class, and until it is, the two
T4 classes are the only ones in the register whose recorded closure is not real.

That contrast is itself the argument for the round: the tool is loudly correct about the
classes nobody claimed to have closed, and silent about the two that were claimed — because
a `rule` string being present is all `check` looks at.

**One process note for the lead, not a finding:** a second fix reviewer (T2) is running in
this same working tree and revert-mutating the same files. That silently corrupted my first
full-suite run and produced one false-green mutation result, both caught and redone
serially. Two reviewers who prove fixes by reverting them cannot share a worktree.
