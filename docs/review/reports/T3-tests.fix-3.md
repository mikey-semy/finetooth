# T3 — fix round 3

The round was handed a design decision, not a list of guard widenings: close the class
*"a class guard keyed on incidental syntax"* with **single entry points** instead of a longer
enumeration of spellings. What follows is that work, measured.

## Verdicts

| finding | verdict | commit |
|---|---|---|
| T3-020 · the NUL rule is blind to `.extend()` argv and to a `_git(*rest)` wrapper | **closed** | `2da3dca` (tool), `c0ee0ec` (guard) |
| T3-021 · the gate registry recognises the refusal list by the variable's name | **closed** | `2da3dca` (tool), `c0ee0ec` (guard) |
| T3-023 · the `--format=` exemption lost a compact one-expression second log parser | **closed** | `2da3dca` (tool), `c0ee0ec` (guard) |
| T3-024 · the meta-guard recognises a real source by three marker strings | **closed** | `c0ee0ec` |
| T3-022 · a guard written onto other blocks' findings | **deferred before this round** (issue #28) | — |

Nothing was rejected. The register carries `--commit c0ee0ec` (the commit that touches the
findings' own file) with `--fixed-in skills/finetooth/scripts/review.py`, and
`--rule tests/test_review.py::SourceMutationTest` — the harness that now proves every source
rule by mutation, the same guard the earlier findings of this root carry.

## What the round did, in one paragraph

Three structural changes to the tool, and the guards became small as a consequence.

1. **`git()` is the only place in the tool that starts a process.** It adds `-z` to every run
   whose output carries paths (`GIT_PRINTS_PATHS`) and reads that output back itself —
   `.fields` for a NUL-separated stream, `.records` for `git grep`. A call site cannot drop
   `-z` because it no longer builds the command line. All 22 git runs were converted.
2. **`log_records` is the only place that orders AND parses the `git log` stream.** It writes
   the `--format` itself, so `LOG_MARK` cannot leave it and a second parser has no marked
   stream to read.
3. **`Refusals` is the only container of refusals in `check`.** A refusal is a pair — the
   gate's own key, written at the call site, and the text a human reads — and `cmd_check`
   returns nothing but `gates.report()`. All 63 gates were given keys
   (`state/no-record`, `finding/code-changed`, `coverage/stale`, …); `GATES` in the suite now
   pairs those keys with tests instead of pairing message skeletons with them.

User-visible behaviour is unchanged: the same messages in the same order, the same exit codes.
Checked on the real tree (`status`, `coverage`, `refs`, `check`, `findings`, `summary`) and on
a stand with a non-ASCII path, below.

---

## T3-020 · the NUL rule blind to two more spellings of argv

**Reproduced on the code as it stood** (HEAD `bbc395d`, the two spellings of the finding
applied to the real call sites, fed to HEAD's own rule):

~~~
T3-020 — the NUL rule at HEAD, fed the two spellings of the finding
  honest tool: []
  -z dropped from untracked_files, argv grown with .extend(): []
  -z dropped from index_rows, argv from a _git(*rest) wrapper: []
~~~

Both spellings silence the rule completely — the defect is real and exactly as described.

**Done.** The question changed. The rule no longer asks how argv was assembled; it asks
whether a process was started anywhere but in `git()`:

* `SourceRuleTest._spawns_outside_git` — every `subprocess.*` spawner, every name pulled in
  from `subprocess`, and `os.system/popen/exec*/spawn*/posix_spawn`, attributed to the
  function that contains it. Only `git()` may.
* `git()` itself inserts `-z` after the subcommand for `ls-files`, `--name-only`,
  `--name-status`, `--others` and `grep`, and exposes `.fields` / `.records`.
* The enumerations that used to carry the class are gone: `ASKS_FOR_NAMES`, `_nul_offenders`,
  `NUL_SHAPES`, `_git_argv_literals`, `_git_without_z`, `_git_prefix_hoisted`, and
  `_Values.built_lists` with them.

**The test that catches it:** `tests/test_review.py::SourceRuleTest::test_процесс_запускают_в_одном_месте`,
plus the `_spawns_outside_git` entry of `SOURCE_MUTATIONS` (spoil: git spawned outside the
helper; respellings: argv accumulated with `.extend()`, argv handed over by a wrapper, the
module under an alias, the spawner pulled in by name).

**Red on the reverted fix** — the finding's own two spellings, applied to the real call sites
of the fixed tool, each in a copy that parses (`ast.parse` asserted before the run):

~~~
── mutant `extend` → tests.test_review.SourceRuleTest
    FAIL: test_процесс_запускают_в_одном_месте
    Ran 12 tests in 1.879s
    FAILED (failures=1)
── mutant `wrapper` → tests.test_review.SourceRuleTest
    FAIL: test_процесс_запускают_в_одном_месте
    Ran 12 tests in 1.313s
    FAILED (failures=1)
~~~

**And the `-z` itself, held by behaviour.** The live consequence the fix review measured —
a C-quoted path in `coverage.tsv` — is now a test:
`GitTruthTest::test_кириллический_путь_записан_в_карту_покрытия_как_есть` builds a stand with
`src/крыша.txt` and `src/plain.txt`, runs `coverage` and requires both names as the index
holds them, with no `\3` escapes and no quote characters in the file. Removing the `-z` that
`git()` inserts (one mutation, the whole tool):

~~~
── mutant `no-z` → GitTruthTest, ReviewToolTest
    Ran 110 tests in 82.825s
    FAILED (failures=36, errors=1)
~~~

Seven of those are `GitTruthTest`, including the new one; before this round the same
consequence left the suite green. That is the ratchet: the property now has one address, and
that address is covered from many sides.

**The other side — what must still be allowed.** argv may be assembled any way at all:
`INSIDE_HELPER` in `test_узда_видит_запуск_мимо_помощника` feeds the rule a hoisted
`_git(*rest)` wrapper whose result is spawned *inside* `git()`, an argv grown with `.extend()`
inside the helper, and a local function of the tool's own called `run` — the rule must stay
silent on all three. The behaviour side is the whole suite: 334 scenarios, every one of which
reads the repository through the new helper.

---

## T3-021 · the gate registry recognises the refusal list by the variable's name

**Reproduced on the code as it stood** (HEAD, a new gate in a module helper whose parameter is
called `refusals` — T3-017's scenario, which the register had recorded as fixed):

~~~
T3-021 — the gate registry at HEAD, fed a gate in a helper whose list is `refusals`
  gates seen before: 63  after adding the new gate: 63
  the new gate got a key: False
~~~

No key, no `UnknownGateSpelling`, no entry demanded — the gate could be deleted later with the
suite green.

**Done.** A gate is no longer a shape of line but a call on the refusals container with its
own key:

* `Refusals.refuse(key, message)` / `.warn(key, message)` in the tool; the key is stored with
  the message and never printed (the user reads the message; the key is what the suite's table
  and the mutation run call the gate by).
* `_check_gates` collects every `*.refuse(...)` / `*.warn(...)` call in the module, wherever it
  stands, and takes the key from the call. A key that is not a string literal is
  `GateWithoutKey` — a refusal, not silence.
* `_own_verdict` — new rule: `cmd_check` returns nothing but `<container>.report()`, and calls
  neither `sys.exit` nor `die` (code 2 is a usage error; a red state is code 1). Without it a
  gate could print its own refusal and return 1, outside every table that counts gates.
* Gone with the class: `_gate_messages`, `_own_nodes`, `_refuse_unknown_spelling`,
  `UnknownGateSpelling`, `LIST_FORM_GATES`, and the message-skeleton keys in `GATES`.

**The tests that catch it:** `GateRegistryTest::test_каждые_ворота_check_записаны_вместе_со_своим_тестом`
(63 keys in the source = 63 entries in `GATES`), `::test_ворота_где_бы_они_ни_стояли_видны_реестру`,
`::test_отказ_без_ключа_роняет_прогон_а_не_молчит`, `::test_приговор_check_выносит_только_контейнер`,
plus the `_check_gates` and `_own_verdict` entries of `SOURCE_MUTATIONS`.

**Red on the reverted fix** — the finding's own scenario against the fixed code, and a gate
that bypasses the container altogether:

~~~
── mutant `helper-gate` (a new gate in a helper whose container is called `refusals`)
    FAIL: test_каждые_ворота_check_записаны_вместе_со_своим_тестом
    Ran 8 tests in 0.344s
    FAILED (failures=1)
── mutant `own-exit` (print + return 1 inside cmd_check)
    FAIL: test_приговор_check_выносит_только_контейнер
    Ran 8 tests in 0.365s
    FAILED (failures=1)
~~~

and the rule's own verdicts on those mutants, for the record:

~~~
  the new gate is registered by the rule: True
  and has no entry in GATES, so the registry goes red: ['blocks/reserved-role']
  a gate that skips the container entirely (print + return 1):
    ['выход `return 1` мимо контейнера']
  a refusal whose key is assembled on the way:
    cmd_check, строка 3049: отказ добавлен без ключа-литерала (`gates.refuse(key, msg)`) — …
~~~

**The other side — what must still be allowed.** Splitting the 500-line `cmd_check` into parts
must keep working: `_gates_split_out` is a respelling in the mutation table in three forms
(a helper taking the container, a helper whose parameter is called `refusals`, a helper nested
inside the command), and every one must leave the 63 keys exactly as they are — the harness
compares the verdict on the honest respelled source against the empty list. Reading the
container (`if gates.problems: …`) must NOT count as a gate:
`::test_чтение_отказов_воротами_не_считается`. And `GateMutationTest` still proves each of the
63 gates by silencing it and by flipping `refuse`↔`warn` in a copy of the tool.

---

## T3-023 · the compact one-expression second parser of the log stream

**Reproduced on the code as it stood** (HEAD's rule, fed the compact form and the same parser
split across two statements):

~~~
T3-023 — the log-mark rule at HEAD, fed a compact one-expression second parser
  compact form (one expression with the format): []
  the same parser split in two statements: [('churn_records', 3744)]
~~~

Exactly the regression the fix review names: the `flows_into` exemption freed the compact form.

**Done.** There is nothing left to tell apart. `log_records(*args)` writes the `--format`
itself and is the only caller of `git("log", …)`, so `LOG_MARK` cannot appear outside it and a
second parser has no marked stream to obtain. `_log_stream_outside_reader` therefore asks two
flat questions: is `LOG_MARK` read outside `log_records`, and is `git log` ordered outside it.
`_Values.flows_into` — the mechanism that lost the compact form — is deleted.

One incidental consequence, named below: `stale_tree` read a commit date with
`git log -1 --format=%ct`; it reads it with `git show -s --format=%ct` now, because reading one
commit's date is not reading the history.

**The test that catches it:** `SourceRuleTest::test_поток_истории_заказывает_и_разбирает_одно_место`
and `::test_узда_видит_свой_разбор_истории_которого_ещё_нет`, plus the
`_log_stream_outside_reader` entry of `SOURCE_MUTATIONS` (spoil: the compact one-expression
parser this finding is about; respellings: the format written as a concatenation, and the
format assembled in advance).

**Red on the reverted fix** — the compact parser added to the fixed tool:

~~~
── mutant `second-log` → tests.test_review.SourceRuleTest
    FAIL: test_поток_истории_заказывает_и_разбирает_одно_место
    Ran 12 tests in 1.500s
    FAILED (failures=1)
~~~

The rule names both halves of the offence, and catches a second stream asked for without the
marker at all:

~~~
['churn_records: маркер записи мимо log_records()', 'churn_records: свой запуск `git log`']
['churn: свой запуск `git log`']
~~~

**The other side.** `log_records` must keep working — it is how `coupling`, `order` and
`summary --aged` read history: `LOG_READER_ONLY` feeds the rule a reader that orders and parses
in one place and a neighbouring `git show --name-only` (not history, not the marker), and the
rule must stay silent on both. Behaviour: `test_переименование_не_обрывает_историю_изменений_блока`,
`test_дрейф_не_считает_один_файл_дважды` and the three `coupling`/`order` tests still pass, and
all of them go red under the `-z` mutant above.

---

## T3-024 · the meta-guard recognises a real source by three marker strings

**Reproduced on the code as it stood** (HEAD, a new rule fed the tool through a path
expression — the finding's own scenario):

~~~
T3-024 — the guard over the guards at HEAD, fed a rule that reads the tool by path
  rules HEAD counts as reading a real source: False
  so the mutation table demands it: False
  by-marker table check would list it as missing: []
~~~

**Done.** What a rule is fed decides nothing now. `SourceRuleTest._rules_without_tables`
recognises a rule by what it DOES: a function that turns text into a tree (`ast.parse`,
`_Values`) and whose verdict reaches a test — through any chain of calls, the first parsing
function on each path. Every such function must be a key in `SOURCE_MUTATIONS`; a rule written
inline in a test is a separate complaint, since there is nothing to feed it. `SOURCE_MARKS`,
`_rules_without_samples`, `_source_through_a_variable` and `SourceMutationTest.NOT_RULES` are
gone — the frontier is the rule set, so no exemption list is needed.

Two rules the marker list had never seen came under the table as a result (both named as
incidental fixes below): `_own_verdict`, and `DocumentedSurfaceTest.subcommands`.

**The test that catches it:** `SourceRuleTest::test_каждое_правило_по_исходнику_доказано_таблицей`
and `::test_узда_видит_правило_которое_никто_не_доказал`, plus the `_rules_without_tables`
entry of `SOURCE_MUTATIONS` (spoil: a rule written inline in a test; respelling: a rule reached
through a relay).

**Red on the reverted fix** — the finding's own scenario against the fixed guard:

~~~
T3-024 — a new source rule fed the tool through a path expression
  the rule is seen: True
  and demanded of the table: ['_new_rule']
  verdict list the mutation harness reports: ['без таблицы: _new_rule']
~~~

and the same shape as an assertion inside the suite: `RULE_SHAPES` holds three cases — a rule
written inline in a test, a rule called through a relay, and a rule fed the tool by a path
expression — and requires a complaint on each. The whole-suite consequence is the mutation
entry above: `SourceMutationTest` spoils the real suite source with an inline rule and requires
the verdict to change.

**The other side — what must still be allowed.** A helper of a rule must NOT need its own
table entry (it is proved together with the rule that calls it): the last assertion of
`test_узда_видит_правило_которое_никто_не_доказал` feeds a rule with a shape helper and
requires exactly `([], ["_new_rule"])`. And a `test_` method that merely CALLS a rule is not a
rule written inline: all twelve rule tests of the suite do that and the guard is silent on
them.

---

## Incidental fixes, each with its own test

Every one of these is a consequence of the three single entry points; none was in the
assignment.

1. **`DocumentedSurfaceTest.subcommands` read the tool itself and could not be fed anything.**
   The new meta-guard found it: it parses the tool's source and its verdict reaches the "every
   command of the tool is named in `SKILL.md`" gate, and it was invisible to the marker list
   twice over (it read the file inside itself, and its name does not start with `_`). It takes
   a source now and reads a command name where it is BUILT (`_Values.literal`), so a name
   hoisted into a variable is still a command.
   *Test:* `DocumentedSurfaceTest::test_узда_видит_команду_имя_которой_собрали_заранее` (both
   sides, including the honest limit: a name that only arrives as an argument is not visible to
   it) and the `subcommands` entry of `SOURCE_MUTATIONS` (spoil: a subparser added with no line
   in `SKILL.md`; respelling: the command name moved into a variable).
2. **A missing `git` reached the user as a traceback.** With one place starting the process
   there is now one place to say it: exit 2 with `git does not run (…) — the kit reads the
   repository through git: install it and repeat the command`.
   *Test:* `GitTruthTest::test_без_git_инструмент_отказывает_а_не_роняет_трейсбек` runs the tool
   with `PATH` pointing at an empty directory. Reverted (the `OSError` branch removed, the copy
   still parses): `FAIL: test_без_git_инструмент_отказывает_а_не_роняет_трейсбек`, `Ran 11
   tests / FAILED (failures=1)`.
3. **`stale_tree` read a commit date through `git log`.** Now `git show -s --format=%ct`: one
   commit's date is not the history, and the history has one reader.
   *Test:* the existing `FreshnessGateTest`. Mutation (the format changed to a non-numeric
   `%cd`, so the date cannot be read): `FAIL: test_origin_по_прежнему_ловит_отставание`,
   `FAIL: test_удалённый_не_origin_ловит_отставание`, `Ran 4 tests / FAILED (failures=2)`.
4. **`review_refs` builds its grep record fields through `GitRun.records`** instead of
   splitting text by hand, and a short record (no line number) no longer costs a traceback.
   *Test:* the existing `test_refs_называет_не_ASCII_путь_как_он_есть` and
   `test_refs_находит_номер_находки_в_коде_и_только_его`; both go red under the `-z` mutant.
5. **Dead mechanisms removed with their classes:** `_Values.built_lists`, `_Values.flows_into`
   and `_Values.uses` (the whole "where does this value flow" machinery the two lost rules
   rested on), `SOURCE_MARKS`, `NOT_RULES`, `_gate_messages`, `_own_nodes`,
   `_refuse_unknown_spelling`, `UnknownGateSpelling`, `_git_argv_literals`, `_git_without_z`,
   `_git_prefix_hoisted`, `_source_through_a_variable`, `_nul_offenders`, `_log_mark_offenders`,
   `_rules_without_samples`. *Test:* the suite as a whole — `_rules_without_tables` refuses a
   table entry for a rule nobody feeds any more (`stale`), so a dangling mutation entry is red,
   not silent.
6. **`SourceMutationTest` gained a control of its own table** in place of the removed
   marker-based check: every entry must carry at least one respelling besides the control one,
   because an entry with a spoil alone proves only that the rule sees the defect where it is
   written plainly — and rules broke on the *respellings*.

## Found, not fixed

* **`restamp` cannot converge on a finding whose file is the register itself.** T3-022's
  `file` is `docs/review/findings.jsonl`; writing the new fingerprint changes the file, so the
  stamp is stale the instant it is written, and `check` keeps reporting the drift. Measured:
  `restamp T3-022` reports "code fingerprint re-taken", and the very next `check` prints the
  same refusal. Not this round's subject (nothing in T3's findings is about `restamp`), and the
  fix is a decision — either exclude `docs/review/` from the code-drift gate, or hash the
  record's own lines rather than the whole file. Left to the lead; worth a finding of its own
  in whichever block owns `restamp`.
* **Three open findings of block T2 went stale because of this round**, and restamping another
  block's records is not a fixer's business. Measured against `bbc395d`: 13 open/deferred
  findings already carried a stale `code_sha` before the round; at HEAD there are 20, of which
  four are the T3 findings closed here (they leave the gate as `fixed`) and three are new —
  **T2-017, T2-018, T2-021**, all on `skills/finetooth/scripts/review.py`, which this round
  restructured. The T2 fixer must re-check them against the new tool: T2-017/018/021 describe
  the tool's own text, not the gate machinery, so the claims should survive, but the line
  numbers will not.
* **`untracked_files` has no observable NUL consequence today.** Its only caller prints the
  COUNT of untracked matches, not the paths, so a C-quoted path there cannot be told from a raw
  one by any behaviour test. It is held by the spawn guard alone. If the message is ever made to
  name the paths (it would help: "the tool sees the index, not the disk" is easier to act on
  with a name), a behaviour test becomes possible.
* **`subcommands` cannot see a command name that only arrives as an argument.** A subparser
  registered through a wrapper (`def add(name): sub.add_parser(name)`) is invisible to it, and
  the documentation gate would pass on such a command. Written down in the test as the rule's
  known limit; closing it means reading the wrapper's call sites, which is a T4 question (the
  documentation gate), not a T3 one.

## Observations outside the assignment

* The gate keys are now a vocabulary of what `check` holds — 63 of them, grouped by subject
  (`state/`, `finding/`, `report/`, `coverage/`, `paths/`, `blocks/`, `manifest/`, `root/`,
  `freshness/`, `refs/`, `findings/`). Nothing prints them today. Two things become cheap if
  they ever should: `check --explain <key>`, and a stable name for a gate in an issue or a
  report — today a gate is quoted by its message, which changes with every wording fix.
* `GIT_PRINTS_PATHS` is the one place where the `-z` rule can still be undone, by deleting a
  subcommand from the list. Three of the five entries are covered by behaviour tests
  (`ls-files`, `--name-only`, `grep`); `--name-status` is covered through `commit_file_sets`,
  and `--others` is not (see above). A list that small, in one place, with a comment saying
  why — that is a different kind of risk from 22 call sites each repeating `-z`.

## What was run

The whole suite, on the working tree of this round:

~~~
$ python3 -m unittest discover -s tests
Ran 334 tests in 465.762s

OK
~~~

The skill format:

~~~
$ npx skills-ref validate skills/finetooth
Valid skill: skills/finetooth
~~~

The tool on the real tree, for the user-visible behaviour the round promised not to change:
`status`, `coverage --no-write`, `refs`, `findings`, `summary`, `check` — same output as
before the round, apart from the fingerprint drift named above.

The state check is red, with 20 refusals and 4 warnings: four blocks whose `block_sha` moved
(T1…T4) and sixteen findings whose `code_sha` moved — 13 of them already stale at `bbc395d`,
three (T2-017, T2-018, T2-021) newly so because this round restructured the tool. No finding of
T3 appears in the refusal list except T3-022, whose drift cannot be stamped away (above). The
fix-debt gate (high and above) is clean.

Mutation runs are quoted next to the findings they belong to; every mutant was parsed
(`ast.parse`) before its run, so "one failed test" cannot be read as "the copy does not build".
