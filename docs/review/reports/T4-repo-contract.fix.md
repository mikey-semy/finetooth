# T4 — Documentation and the repository contract · fix report

18 findings handed over, **18 closed, 0 rejected**. Every defect was reproduced on the
current code before the fix; every fix that could be tested carries a test proven red on the
reverted code, and — where the fix forbids something — a second test proving that what was
allowed still passes.

## Findings → verdict → commit

| Finding | Verdict | Commit | Guard |
|---|---|---|---|
| T4-001 · medium · SKILL.md licence | closed | `25a5421` | `SkillFormatTest::test_поле_лицензии_это_её_обозначение_и_ничего_сверх` |
| T4-003 · medium · SECURITY boundary | closed | `002dbf1` | `WriteBoundaryTest::test_ни_одна_команда_не_пишет_вне_каталога_ревью` |
| T4-016 · medium · `init` traceback | closed | `02543ab` | `HandWrittenInputTest::test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении` |
| T4-002 · low · NOTICE anonymisation | closed | `9c66593` | — (see "not guarded") |
| T4-004 · low · test count and runtime | closed | `9c66593` | `RepositoryContractTest::test_число_сценариев_в_документах_равно_настоящему` |
| T4-005 · low · coupling thresholds in README | closed | `9c66593`, `fe08bbd` | `RepositoryContractTest::test_пороги_из_документов_читаются_из_кода` |
| T4-006 · low · CHANGELOG contradicts itself | closed | `9c66593`, `fe08bbd` | `RepositoryContractTest::test_пороги_из_документов_читаются_из_кода` |
| T4-007 · low · proposal template | closed | `9c66593` | `RepositoryContractTest::test_живое_руководство_ведёт_на_существующие_пути` |
| T4-008 · low · missing compare links | closed | `9c66593` | `RepositoryContractTest::test_у_каждой_версии_в_истории_есть_ссылка_на_сравнение` |
| T4-009 · low · "all mechanical" gates | closed | `9c66593`, `fe08bbd` | `RepositoryContractTest::test_каждые_объявленные_ворота_гоняет_ci` |
| T4-010 · low · DCO unenforced | closed | `9c66593` | `DcoGateTest` (5 tests) |
| T4-011 · low · README.ru parity | closed | `9c66593` | — (see "not guarded") |
| T4-012 · low · incomplete inventory | closed | `9c66593` | `RepositoryContractTest::test_опись_набора_называет_все_команды`, `…все_файлы_скилла_и_корня` |
| T4-013 · low · RELEASING paths | closed | `9c66593` | `RepositoryContractTest::test_живое_руководство_ведёт_на_существующие_пути` |
| T4-014 · low · unpinned action | closed | `9c66593` | `RepositoryContractTest::test_действия_ci_закреплены_коммитом` |
| T4-015 · low · Russian workflow | closed | `9c66593` | `RepositoryContractTest::test_в_github_нет_кириллицы` |
| T4-017 · low · Python versions unverified | closed | `9c66593` | `RepositoryContractTest::test_версии_python_из_шапки_скилла_прогоняются_в_ci` |
| T4-018 · low · codes of conduct not cross-linked | closed | `9c66593` | `RepositoryContractTest::test_у_двуязычных_файлов_ссылка_друг_на_друга_в_первой_строке` |

All guards live in `tests/test_review.py`.

---

## T4-016 · `init` answered a traceback on a hand-written definition

**Probe before the fix.** A `blocks.json` with a valid block and no top-level `review_id`,
every subcommand run over it on a clean repository:

```
--- init: exit=1
      File ".../review.py", line 564, in cmd_init
        st = {"review_id": defn["review_id"], "updated_at": now(), "blocks": {}}
    KeyError: 'review_id'
--- status: exit=2   error: docs/review/state.json is missing — run `… init`
--- check:  exit=2   (same)
--- coverage: exit=0
```

**The whole class, measured** (same probe, eight malformed shapes × every subcommand). Three
shapes produced a traceback, not one:

| shape | commands that died | how |
|---|---|---|
| no top-level `review_id` | `init` | `KeyError: 'review_id'` |
| exclusion written with `reason` and no `pattern` | `check`, `coverage`, `order`, `coupling` | `KeyError: 'pattern'` |
| `exclusions` written as one object | the same four | `TypeError: string indices must be integers` |
| `pattern` not a string | the same four | `TypeError: expected str … not int` |
| `paths` written as a string | `coverage`, `order`, `coupling`, `summary` | `TypeError: can only concatenate list` |
| `paths` with a non-string element | the same, plus `check` | `TypeError: expected str … not int` |

**What was done.** `check_definition` (`skills/finetooth/scripts/review.py`) now validates the
top-level `review_id`, the shape of `exclusions` and of each entry's `pattern`, and `paths` /
`ref_paths` as lists of non-empty strings. Each refusal is exit 2 and names the field, the
file and the example.

**Why the guard was green.** `HandWrittenInputTest.test_ни_одна_команда_не_роняет_трейсбек…`
called every subcommand as `<cmd> H1 s.md`. `init` takes neither a block id nor a file name,
so argparse rejected the call before `cmd_init` ran, and the traceback the guard exists to
forbid went past it for as long as the guard existed. The guard now calls each command **with
and without** those arguments, over a table of eleven damaged definitions, so a new field
falls under the rule the way a new command already did.

**Revert.** The tool restored to `HEAD` (`git show HEAD:…/review.py`); it compiles
(`py_compile`, no unused-variable breakage), and the guard goes red at many addresses:

```
FAIL: … (cmd='init', args=(), порча='нет review_id')
FAIL: … (cmd='coverage', args=(), порча='исключение без pattern')
FAIL: … (cmd='order', args=(), порча='paths строкой')      … 30+ subtests
FAIL: test_отказ_на_битом_определении_называет_поле_и_файл (порча='нет review_id')
```

**The other side.** `test_целое_определение_по_прежнему_принимается`: an exclusion carrying
extra keys, a block with no `paths`, a definition with no `exclusions` — all still exit 0.
Measured directly as well: `init` on each of those shapes prints `state initialised: 1 blocks`.

---

## T4-003 · the security boundary was false in both directions

**Probe before the fix.** `SUMMARY_DEFAULT = "docs/review-summary.md"` (`review.py:1271`),
written at `1417-1421`; on a clean stand `summary` with no arguments creates
`docs/review-summary.md` — outside `docs/review/` — and `summary --out <path>` writes outside
the repository. `assets/run-role.sh:25` writes the prompt and the event stream into
`$TMPDIR/finetooth-runs`; `:38` pipes the prompt into `claude -p`. `SECURITY.md:3` promised
"writes to `docs/review/` and sends nothing over the network", and `SECURITY.md:15` calls a
write outside `docs/review/` a reportable vulnerability — i.e. the file classified its own
intended behaviour as a hole.

**What was done.** `SECURITY.md` now states, per part of the kit, what is written and what is
sent: `review.py` under `docs/review/` plus the summary the user asks for by name; `setup`
never overwrites; `run-role.sh` is the opt-in exception that keeps the prompt and the stream
in `$TMPDIR` and sends the prompt over the network (with the honest alternative —
`review.py prompt` prints the same text and sends nothing); `axes.py` writes nothing.

**Guard — a run, not proof-reading.** `WriteBoundaryTest` snapshots the project tree
(everything outside `.git/` and `docs/review/`, by content hash), calls **every** subcommand
taken from `--help`, and fails on anything created or modified outside the review directory.
The one allowed exception is named in the test and asserted to be named in `SECURITY.md` too,
so the rule and the promise cannot drift apart.

**Mutations.**

```
one write site pointed at the repository root:
  AssertionError: Items in the first set but not the second:
  'coverage-copy.tsv' : файлы появились вне docs/review/ — SECURITY.md этого не обещает
the old SECURITY.md restored:
  AssertionError: … : SECURITY.md не называет docs/review-summary.md
```

**The other side.** `test_итог_пишется_туда_куда_сказали_и_только_туда`: `summary` still
writes `docs/review-summary.md`, and `summary --out` still writes to a path outside the
repository (a Cyrillic file name in a temporary directory), while nothing else appears.

---

## T4-001 · the skill's licence field

**Probe.** `skills/finetooth/SKILL.md:4` read `license: MIT for the additions; the base was
handed over by its author without a license — full terms in LICENSE`. `LICENSE` is plain MIT
with both holders and is byte-identical to `skills/finetooth/LICENSE`; `NOTICE.md:20-27`
records the 24.09.2026 grant. The installed copy therefore told a reviewer that part of the
kit could not be licensed.

**What was done.** The field is the licence identifier and nothing else (`license: MIT`);
prose about origin and consent stays in `LICENSE` and `NOTICE.md`.

**Guard and mutation.** `test_поле_лицензии_это_её_обозначение_и_ничего_сверх` reads the
identifier out of `LICENSE`'s first line and compares. With the old sentence restored:

```
AssertionError: 'MIT for the additions; the base was handed o[55 chars]ENSE' != 'MIT'
```

**Still allowed.** The skill validates: `skills-ref validate` → `Valid skill` (see "What was
run"), `license` being an allowed frontmatter field.

---

## T4-010 · the DCO, and T4-009 · the release gates

**Probe.** `git ls-files .github` → nine files, none a DCO job; the only workflow on
`pull_request` ran the suite and the validator; `.github/PULL_REQUEST_TEMPLATE.md:13` is a
self-reported checkbox. `RELEASING.md:23` said "Gates — all mechanical, all before the tag"
while gate 3 says of itself that it cannot be automated, and `CONTRIBUTING.md:59` repeated
"four mechanical gates" — a second address of the same claim, fixed with it.

**What was done.**

- `.github/dco.sh` — git and bash only. A commit passes when its message carries
  `Signed-off-by: … <author's own email>`; merge commits are skipped, since they carry
  nobody's authorship of the code. The refusal names the commit and the way out
  (`git rebase --signoff`, `git commit -s`, CONTRIBUTING).
- A `dco` job runs it on every pull request (`fetch-depth: 0`); CONTRIBUTING documents the
  local invocation.
- `RELEASING.md` now says of each gate who runs it and what in it cannot be automated, and
  why the wording is there at all (three releases shipped without compare links).

**Tests — both directions.**

| test | direction |
|---|---|
| `test_коммит_без_подписи_роняет_ворота_и_называет_починку` | forbidden no longer passes |
| `test_подпись_с_чужой_почтой_не_засчитывается` | a sign-off copied from a neighbour is not a sign-off |
| `test_подписанные_коммиты_проходят` | **allowed still passes**: several authors in one branch, an address typed in another case |
| `test_коммит_слияния_подписи_не_требует` | **allowed still passes**: `git merge` does not sign off |
| `test_рабочий_процесс_зовёт_эти_ворота` | a script nobody calls is not a gate |

**Mutation.** The author-email requirement dropped from the grep →
`test_подпись_с_чужой_почтой_не_засчитывается` red (`AssertionError: 0 != 1`).

---

## T4-014, T4-015, T4-017 · the CI workflow

**Probe.** `.github/workflows/tests.yml:15` used `actions/checkout@v5` while `stale.yml:19`
and the `skills-ref` install are pinned by commit; steps and comments were Russian
("Настроить git", "Прогнать тесты", "Проверить формат скилла") in a repository whose rule is
English with `.ru.md` copies; no `actions/setup-python` and no matrix, so the suite ran on
whatever `python3` the runner image carried, against `SKILL.md`'s "tested on 3.12 and 3.14".

**What was done.** `actions/checkout` pinned at `fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09`
(v5.1.0) and `actions/setup-python` at `ece7cb06caefa5fff74198d8649806c4678c61a1` (v6.3.0),
both resolved from the GitHub API; every step and comment in English; a matrix over exactly
the versions the skill declares; the skill validator split into its own job so it runs once.

> **For the maintainer:** the job names change — `unittest (3.12)`, `unittest (3.14)`,
> `skill`, `dco`. If branch protection requires a check named `unittest`, it has to be
> updated with this merge, or the requirement will match nothing. Said in the CHANGELOG too.

**Mutations.** `checkout@v5` restored → `test_действия_ci_закреплены_коммитом` red
(`['tests.yml:22 actions/checkout@v5', …]`); the old Russian workflow restored →
`test_в_github_нет_кириллицы` red (`['.github/workflows/tests.yml']`) and
`test_рабочий_процесс_зовёт_эти_ворота` red; a version dropped from the matrix →
`test_версии_python_из_шапки_скилла_прогоняются_в_ci` red.

**Locally verifiable half.** The suite is green on 3.14 (the only interpreter on this
machine); 3.12 is exercised by the matrix in CI and by nothing here.

---

## T4-004, T4-005 · numbers that were no longer measurements

**Probe.** `python3 -m unittest discover -s tests` → `Ran 248 tests in 189.741s`
(`real 3m9s`), against "Ninety-eight scenarios" / "98 scenarios, about a minute" in
`README.md:281,438`, `README.ru.md:228,377`, `AGENTS.md:68`, `CONTRIBUTING.md:65`. `coupling`
on a 9-block fixture printed `hub = coupled with >= 3 blocks` and
`Tukey's fence over 17 commits — fewer than 20, too few for a percentile`, against the
README's "a file coupled with six or more blocks" and a bare 95th percentile.

**What was done.** The count and the runtime re-measured in all five places (270 scenarios,
about five minutes — the suite grew by this block's guards); the coupling paragraph now
describes the rules the tool has, in both languages.

**Guards.** `test_число_сценариев_в_документах_равно_настоящему` takes the count from the
suite itself (`defaultTestLoader.discover(...).countTestCases()`) — the documents cannot drift
again. `test_пороги_из_документов_читаются_из_кода` reads `COUPLING_*` out of `review.py` and
requires each document that quotes a threshold to state it.

**Mutation.** `COUPLING_HUB_SHARE` moved to 0.25 →
`не описывает COUPLING_HUB_SHARE = 0.25 (ожидалось одно из ['a quarter', 'четверти част'])`,
red for both READMEs. Any document left at the old scenario count → red with the real number.

**Not held by a test:** the runtime ("about five minutes"). It depends on the machine; it is
labelled as measured on the author's machine, and `AGENTS.md` says which half a test holds.

---

## T4-006, T4-008 · the CHANGELOG

**Probe.** `CHANGELOG.md:68` (Added) said a shared node is a file coupled with ≥ 6 blocks;
`:36` (Fixed) said the threshold is a share with a floor of three — one section, two
mutually exclusive rules for one mechanism, and release notes are taken from it verbatim.
Parsing both files: ten version headings, seven link references — `0.5.1`, `0.5.0` and `0.4.1`
had none in either language.

**What was done.** The Added entry states the shipped rule; the Fixed entry keeps the
justification without reading as a change to a released mechanism. The three missing compare
links added in both languages, and `[0.6.0]` now compares from `v0.5.1` instead of skipping
it (all nine tags exist: `git tag`).

**Guard and mutation.** `test_у_каждой_версии_в_истории_есть_ссылка_на_сравнение` parses
headings and link references from both files. On the previous content:
`AssertionError: Lists differ: ['0.5.1', '0.5.0', '0.4.1'] != []`.

---

## T4-007, T4-013 · guidance pointing at files that do not exist

**Probe.** `git ls-files docs` lists only `docs/review/`; `.github/ISSUE_TEMPLATE/proposal.yml:16`
sent contributors to `docs/prior-art.md` and `:22` asked for a ROADMAP direction number, both
in the private knowledge base. `RELEASING.md:50` named `scripts/review.py` and a root
`SKILL.md`; `git ls-files` has no entry under `scripts/` and no root `SKILL.md` — the layout
moved into `skills/finetooth/` in 0.4.0.

**What was done.** The release step names the real paths and notes that a test compares the
two version strings. The proposal template asks "How it would be proven" — the gate that
would go red and the mutation that proves it — and says plainly that the plan is in a private
knowledge base, so nobody invents a direction number.

**Guard and mutation.** `test_живое_руководство_ведёт_на_существующие_пути` reads path-shaped
tokens (anything containing a `/`) out of `RELEASING.md` and the `.github` templates and
requires them to exist. With both files reverted:
`Lists differ: ['RELEASING.md:50 scripts/review.py', '.github/ISSUE_TEMPLATE/proposal.yml:16 docs/prior-art.md'] != []`.

Bare names (`blocks.json`, `SKILL.md`) are deliberately outside the rule: documents name them
informally and they are not repository-root paths. That is why the root `SKILL.md` half of
T4-013 is held by the corrected text and not by the rule — noted under "not guarded".

---

## T4-012 · the inventory

**Probe.** `--help` registers 23 subcommands; `README.md:421-423` and `README.ru.md:360-362`
listed 19, and `refs` appeared nowhere in either README. The tree omitted `scripts/axes.py`
and `assets/run-role.sh` — the two files that write outside the repository — all ten `.ru.md`
templates and assets the `lang` switch selects, and at root `.gitignore`, `CLAUDE.md`,
`LICENSE`, `CHANGELOG.ru.md`, `CODE_OF_CONDUCT.ru.md`.

**What was done.** Both trees list all 23 commands, every file of the skill (the `.ru.md`
copies grouped but each named), `.github/`, and every tracked root file.

**Guards.** `test_опись_набора_называет_все_команды` takes the command list from `--help`;
`test_опись_набора_называет_все_файлы_скилла_и_корня` takes the file list from
`git ls-files`. Both read the truth from the tool and the index, so a new command or a new
asset falls under the rule without the test being edited — the same shape as the existing
class guards.

---

## T4-011 · the Russian README

**Probe.** `README.md:34-52` carries the six claims that separate the kit from PR-review bots
and the "Language" paragraph; `README.ru.md` had neither (its outline goes from the badges
straight to "Зачем это нужно"), while `[Русская версия]` at the top of `README.md` is the only
entry point offered to a Russian reader.

**What was done.** The four-roles paragraph, the six guarantees and the Language paragraph
added to `README.ru.md` in the same place as in the English file.

**Not guarded, deliberately.** Prose parity is not mechanically checkable: a guard comparing
`##` headings passes on exactly this defect (both files had the same headings throughout).
Counting bold-lead paragraphs would be a guard on formatting, not on meaning. Left to review.

---

## T4-002 · NOTICE

**Probe.** `NOTICE.md:31` promised that the names of the projects the method was road-tested
on, their internals and the defects found are not published. `CHANGELOG.md:40` and
`CHANGELOG.ru.md:40` name `setfork H3` with the path `curation/adapter.ts`; the same path is
in `review.py` and in the tests, shipped inside the skill. The project is the repository
owner's own, so no third party's data is disclosed — but the sentence was false, and a
CHANGELOG is never deleted.

**What was done.** The promise is scoped to what the repository actually does: someone else's
project is never named — the project the method was worked out on and anything reviewed for
anyone but the owner; the owner's own projects are named, with the paths a number needs to be
traceable, because a measurement whose origin cannot be checked is not a measurement.

**Not guarded.** A rule cannot tell someone else's project name from the owner's own; a list
of forbidden names would have to contain the very names the promise is about. Left to review.

---

## Incidental fixes, each named

1. **`CONTRIBUTING.md:59` repeated "four mechanical gates"** — a second address of T4-009
   found by grep, not by the finding. Fixed with it; held by the same guard
   (`test_каждые_объявленные_ворота_гоняет_ci`), which reads the gate commands out of
   CONTRIBUTING itself.
2. **`[0.6.0]` compared from `v0.5.1`'s predecessor**, skipping 0.5.1 — found while fixing
   T4-008's missing links. Fixed; the link guard holds the presence of every reference, and
   the diff of the correction is one line.
3. **`CONTRIBUTING.md` now documents the local DCO invocation** — without it the new gate
   would first run on a stranger's pull request. Held by
   `test_каждые_объявленные_ворота_гоняет_ci`, which requires every command in those blocks
   to be run by a workflow.
4. **The skill validator moved into its own CI job.** With a Python matrix it would otherwise
   have installed and run three times over. No behaviour change; covered by the same gate
   guard, which requires `validate skills/finetooth` to appear in the workflows.

## Two classes closed by a rule

The tool itself named both (`review check`): a class that repeated three times is closed by a
rule, not by a list of fixed places.

| root | instances | rule | goes red on |
|---|---|---|---|
| a number in a public document not checked against its source | T4-004, T4-005, T4-006 | `test_пороги_из_документов_читаются_из_кода` + `test_число_сценариев_в_документах_равно_настоящему` | `COUPLING_HUB_SHARE` → 0.25 with the text unchanged; any document left at the old scenario count |
| a rule declared enforced with nothing enforcing it | T4-009, T4-010, T4-017 | `test_каждые_объявленные_ворота_гоняет_ci` | the `dco` job removed; the validator step replaced by `true` |

Both rules read their subject from the source rather than from a list: the thresholds from
`review.py`, the count from the suite, the gate commands from `CONTRIBUTING.md`'s own `sh`
blocks. A new threshold or a new declared gate falls under them without the tests being
edited.

## Found, not fixed — for the lead

**A different kind of defect, so a finding rather than a fix inside someone else's:**

- `blocks.json` with `"gates": "make test"` (a string instead of a list) produces no
  traceback and no refusal: `prompt` renders the string one **character** per bullet, and the
  agent receives a prompt whose gate list is nonsense. Measured on the same stand as T4-016.
  It is not the traceback class, and refusing it would newly reject a definition that a live
  review may be running with — the decision is the lead's, and it needs a Breaking line if
  taken. Address: `review.py` (`"{{GATES}}"` substitution) and `check_definition`.
- `README.md:54-64` repeats the opening: the "The kit turns the request…" paragraph and the
  "The kit is a skill under the open standard…" paragraph restate lines 17-26 almost word for
  word. Harmless, but the Russian file now mirrors the same repetition because parity was the
  finding. Worth one editing pass, in both languages at once.
- `README.md:147` and `README.ru.md:134` cite `example/makefile-snippet.mk`; the file is
  `skills/finetooth/assets/makefile-snippet.mk`. Outside the live-guidance rule's scope (the
  README is not a "do this now" document and the rule would drown in examples from other
  projects). One line in each language.

**Observations outside the assignment:**

- `.github/PULL_REQUEST_TEMPLATE.md:13` still asks the author to confirm the sign-off by
  checkbox. Now that CI checks it, the line could say so — or go. Not touched: it changes what
  contributors see and is the maintainer's call.
- Both workflows pin `actions/checkout` at v5.1.0 and `actions/setup-python` at v6.3.0, while
  v7 exists for both. Pinning was the finding; upgrading is a separate decision and belongs to
  the maintainer (rule 11).
- The suite now takes about five minutes, up from about three: the two sweeping guards added
  here (`HandWrittenInputTest`'s damage table ≈ 500 tool invocations,
  `WriteBoundaryTest`'s full subcommand sweep) account for it. Cheap to trim if the runtime
  starts to hurt — the damage table is the lever.

## What was run

**The suite**, from the repository root, after the last commit:

```
$ python3 -m unittest discover -s tests
..............................................................................
----------------------------------------------------------------------
Ran 270 tests in 298.664s

OK

real    4m58.791s
```

**The skill format.** `skills-ref` is not installed on this machine and `pip install` is
refused by this environment, so the validator was run from its own source at the commit CI
pins (`agentskills@69ef37e…`, `skills-ref/src/skills_ref/validator.py`), with a minimal
stand-in for `strictyaml` — everything that decides valid/invalid is upstream's own code:

```
✓ /home/mike/Projects/finetooth-wt-fix-t4/skills/finetooth: Valid skill
```

The runner was checked not to pass vacuously: on a copy of the skill with `name:` changed and
`license:` misspelled it reports

```
- Unexpected fields in frontmatter: licence. Only [...] are allowed.
- Skill name 'Not-The-Dir' must be lowercase
- Directory name 'badskill' must match skill name 'Not-The-Dir'
```

CI runs the real `skills-ref validate skills/finetooth` in the `skill` job.

**The kit on itself:**

```
$ python3 skills/finetooth/scripts/review.py refs
no finding of the register is named outside docs/review/

$ python3 skills/finetooth/scripts/review.py coverage
covered:     71/71 files
no unowned files
```
