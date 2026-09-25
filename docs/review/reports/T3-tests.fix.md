# T3 — fix report: tests as the gate

15 findings, each re-checked against the current code before it was touched. All 15
closed, none rejected; two mechanisms named inside T3-007 were left unmeasured and are
listed at the end. Four guards were widened and three new ones written, because every
finding of this block is the same shape: a rule that held one spelling, and the next
spelling walked past it.

Every fix is proven by mutation: the mechanism broken in a copy of the kit, the named test
run against that copy, and both the build result and the test result read. The mutation
runs are quoted at the end.

**How to read the table.** "Red on revert" means the mutation in that row turned the named
test red while the mutated copy still compiled and the rest of the suite still ran — a test
that also passes on the old code guards nothing.

**A note on this file.** It is a report of the block, so the tool parses it for hypothesis
verdicts. Every quoted output is inside a fence, and words of the verdict vocabulary are
avoided outside them.

## Commits

| commit | what is in it |
|---|---|
| `a6d7df3` | Gate registry: every gate is tied to its test by mutation, not by a name |
| `18f5770` | The suite's verdict must not depend on the machine it runs on |
| `3720b2a` | Guards that a plausible new shape of code walked past |
| `f8007b3` | Mechanisms outside `cmd_check`, each with the test it was missing |
| `44b884c` | this report, the changelog and the register |

## The findings

| id | verdict | commit | what closed it |
|---|---|---|---|
| T3-001 | closed | `a6d7df3` | `refused()`/`warned()` in 47 gate tests + the flip mutation guard |
| T3-002 | closed | `a6d7df3` | `_gate_messages` reads every spelling; an unknown one is a refusal |
| T3-003 | closed | `a6d7df3` | `GateMutationTest`: the named test must go red on the silenced gate |
| T3-004 | closed | `f8007b3` | a test for backfill idempotence and one for set-finding atomicity |
| T3-005 | closed | `f8007b3` | per-command argv, and a new command without one fails the suite |
| T3-006 | closed | `3720b2a` | the two `MSG` tables and the two-language files compared |
| T3-007 | closed | `f8007b3` | tests for six mechanisms; two left unmeasured, named below |
| T3-008 | closed | `18f5770` | the test proves both sides; `Stand.commit` no longer fails in silence |
| T3-009 | closed | `18f5770` | `child_env()` for every child + the CI locale + a refusal naming the fix |
| T3-010 | closed | `18f5770` | `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` off, the branch named by the stand |
| T3-011 | closed | `f8007b3` | the `claude` stub emits the same stream as a real run |
| T3-012 | closed | `3720b2a` | the NUL rule assembles argv per call, across concatenation and variables |
| T3-013 | closed | `3720b2a` | `named_file()` + a source rule keeping names out of pathspecs |
| T3-014 | closed | `3720b2a` | the threshold rule reads any expression and tuple assignment |
| T3-015 | closed | `18f5770` | `sys.executable` everywhere + a source rule over the suite itself |

---

## T3-001 · medium · a gate moved from `problems` to `warnings` leaves the suite green

**Re-checked:** reproduced on the current code. The block-status gate rewritten as
`warnings.append(...)`, then its named test and the registry run:

~~~
Ran 5 tests in 0.467s
OK
~~~

`check` then prints the same sentence and exits 0 on the state it refused. Measured across
all 63 gates: **47 of them survived the flip** — 45 problem gates whose tests never look at
the exit code, and 2 warning gates whose tests would not notice becoming refusals.

**Done:** two helpers, `refused(out)` and `warned(out)`, return the CHECK FAILED section
(only when the run failed) and the WARNINGS section (only when it did not). Every gate test
now asserts WHICH section its message landed in. The exit code alone is not enough: on a
fixture where a second gate also fires, `check` exits 1 anyway — measured on
`test_манифест_пропал_а_блок_в_работе`, which asserts the exit code and still survived the
flip.

**Commit:** `a6d7df3`
**Test:** `GateMutationTest.test_названный_тест_краснеет_когда_ворота_сменили_строгость`
holds the class for all 63 gates at once; the 47 rewritten tests hold each gate.
**Red on revert:** yes — the five gates the finding names, each moved to `warnings` in a
copy, build ok:

~~~
RED    test_статус_блока_вписанный_руками_роняет_проверку
RED    test_куцый_манифест_роняет_проверку
RED    test_фазы_в_массиве_не_убывают
RED    test_шаблон_который_ничего_не_нашёл_роняет_проверку
RED    test_третий_повтор_корня_требует_узду
~~~

**The other side:** a warning must stay a warning. `test_check_предупреждает_о_находке_старше_недели`
and `test_refs_находит_номер_находки_в_коде_и_только_его` now assert through `warned()`,
which is empty unless the run exited 0 — so a warning promoted to a refusal turns them red.
Both directions are covered for every gate by the flip mutation, which runs in both
directions by construction.

---

## T3-002 · medium · a gate written with `+=` or `extend` needs no test

**Re-checked:** reproduced — a gate added to `cmd_check` as
`problems += [f"{bid}: role \`__never__\` is reserved"]` produced no registry key, and
the registry stayed green.

**Done:** `_gate_messages()` reads every spelling that adds to the refusal lists —
`append`, `extend`, `+=`, `problems = problems + [...]` — and each message in a list gets
its own key. A spelling the registry does not know is no longer silence: `_check_gates`
raises `UnknownGateSpelling` naming the line and the way out.

**Commit:** `a6d7df3`
**Test:** `GateRegistryTest.test_ворота_написанные_списком_видны_реестру` (all three list
forms) and `test_незнакомая_форма_записи_отказ_а_не_молчание`.
**Red on revert:** yes — the same gate added to the real `cmd_check` in both spellings,
build ok, registry red both times:

~~~
RED    registry on a gate written with +=
RED    registry on a gate written with .extend
~~~

**The other side:** an ordinary f-string gate is still keyed by its text, not by its
expression — `test_ворота_с_литеральным_сообщением_читаются_как_раньше` — and reading the
list (`if problems:`, `for p in problems`) is not a gate: the same test asserts an empty
result for the tail of `cmd_check`.

---

## T3-003 · medium · a registry entry pointing at any existing test satisfies the guard

**Re-checked:** reproduced — the entry for `: no manifest` re-pointed at the unrelated
`test_описание_в_пределах`, both registry tests green.

**Done:** `GateMutationTest` silences each gate in a copy of the tool — the statement
replaced by `pass`, so the mutant still compiles — and requires the test named beside it to
go red on that copy. 63 gates × 2 mutations run in 23 s on eight workers. The guard skips
itself when the suite is already running against a mutant (`FINETOOTH_TOOL` set), which is
also how the harness points a child at the mutated tool.

**Commit:** `a6d7df3`
**Test:** `GateMutationTest.test_названный_тест_краснеет_когда_ворота_сняты`.
**Red on revert:** yes — with the `: no manifest` entry re-pointed at
`test_описание_в_пределах`, the guard goes red (`FAILED (failures=2)`): the entry is
silenced and the test it names notices nothing.

**The other side:** every one of the 63 registered tests really does hold its gate — the
whole harness is green on the honest registry, which is the "allowed" half of the same
measurement.

**A defect found in the guard itself, and fixed.** The harness first copied `review.py`
alone. A copy of one file has no `references/` and no `assets/`, so every test that
assembles a prompt goes red on it for that reason — and "the named test went red" would
then prove nothing about the gate. Measured: with a one-file copy, all 62 tests named in
the registry are still green (they need no templates), so the verdicts above stand; but the
harness copies the whole skill now, and `test_на_целой_копии_все_названные_тесты_зелены`
runs every named test on an untouched copy and requires green. Without that control, a
guard that demands red is satisfied by any breakage at all.

---

## T3-004 · medium · backfill idempotence and set-finding atomicity held by nothing

**Re-checked:** `backfill` ran exactly once in the whole suite, and `set-finding` over
several ids only on the happy path. Both invariants are named in the project invariants
(11), and neither had a test.

**Done:** no product change — both mechanisms are correct; they were untested.

- `IdempotenceTest.test_повторный_backfill_на_проставленном_состоянии_ничего_не_пишет`:
  the first run stamps, the second must print "nothing to stamp" and leave `state.json`
  and `journal.md` byte for byte as they were.
- `ReviewToolTest.test_set_finding_на_нескольких_номерах_всё_или_ничего`: a refusal on the
  second id — an unknown id, and `fixed` without a commit — leaves the register untouched;
  the same command without the bad id moves both findings.

**Commit:** `f8007b3`
**Red on revert:** yes, both, each with a control run on an untouched copy of the skill:

~~~
RED   backfill: the early return on a clean state
        killed by: test_повторный_backfill_на_проставленном_состоянии_ничего_не_пишет
green     control (untouched copy)
RED   set-finding: the register written inside the loop
        killed by: test_set_finding_на_нескольких_номерах_всё_или_ничего
green     control (untouched copy)
~~~

**The other side:** `backfill` must still stamp what is missing (the first run in the same
test asserts it names the block), and `set-finding` over several ids must still move them
all — the tail of the atomicity test, plus the existing
`test_set_finding_переводит_несколько_находок`.

---

## T3-005 · low · the no-traceback guard fed one argv to every command

**Re-checked:** reproduced by running the guard's own loop — of the 23 commands it takes
from `--help`, 20 exited 2 with `unrecognized arguments` before their body started, so for
those the guard asserted the absence of a traceback from argparse's usage error.

**Done:** the guard carries an argv per command — the arguments with which the command
reaches its body — and refuses an unlisted one, so a new command still falls under the rule
without silently slipping out of it. Two more assertions state what "reached the body"
means: the stderr must not say `unrecognized arguments`, `the following arguments are
required` or `invalid choice`.

**Commit:** `f8007b3`
**Test:** `HandWrittenInputTest.test_ни_одна_команда_не_роняет_трейсбек_на_битом_определении`.
**Red on revert:** yes, twice, build ok both times:

~~~
RED   a command body raising on a broken definition (cmd_sizes)
RED   a new subcommand with no entry in the argv table
~~~

The first is the defect the guard promises to catch and could not: with one argv, `sizes`
never started. The second is the promise in its docstring.

**The other side:** all 23 commands do reach their bodies on a hand-written broken
definition and refuse with a message rather than a traceback — that is what the test
asserts now, and it passes.

---

## T3-006 · low · a string in one language and not in the other

**Re-checked:** reproduced — `MSG["ru"]["refs_cut"]` deleted, whole suite green. The
tables are in sync today (58 keys each), so this is a missing guard, not a live defect.

**Done:** `LanguageTest.test_обе_языковые_таблицы_держат_одни_ключи_и_подстановки`
compares the key sets of every language and, for every key, the set of substitution fields
— a translation with a renamed field fails in `format` just as loudly as a missing key.
The same class covers files: `test_у_каждого_шаблона_и_образца_есть_второй_язык` requires
every markdown in `references/` and `assets/` to have its twin.

**Commit:** `3720b2a`
**Red on revert:** yes, build ok:

~~~
RED   ru refs_cut deleted
RED   ru placeholder renamed ({n} -> {count})
RED   hunter.ru.md removed
~~~

**The other side:** the guard passes on the current tables, and it does not ask for a twin
of anything that is not markdown (`blocks.example.json`, the snippets, the two shell
scripts) — the test reads only `*.md`.

---

## T3-007 · low · mechanisms outside `cmd_check` that no test reaches

**Re-checked:** six of the eight mechanisms the finding names were re-measured, each
broken in a full copy of the skill with only the test named for it run against that copy,
and each with a control run on an untouched copy so that a red verdict cannot mean "the
copy is broken". The run is quoted at the end.

**Closed** — each mechanism now has a test named for it:

| mechanism | test |
|---|---|
| `import`'s claim cap | `test_импорт_держит_те_же_потолки_что_и_проверка` |
| `block_risk`'s refusal | `test_риск_вне_словаря_это_отказ_а_не_трейсбек` |
| `review_lang`'s fallback | `test_язык_которого_нет_не_роняет_инструмент` (commit `3720b2a`) |
| `cmd_next` | `test_next_называет_следующий_незакрытый_блок` |
| `restamp` on a vanished file | `test_restamp_на_пропавшем_файле_отказ_а_не_отпечаток_пустоты` |
| `guard-grep`'s `--exclude` | `test_исключение_снимает_попадание_а_остальные_оставляет` |

`guard-grep --exclude` is the one the finding lists as unmeasured that really was a
survivor: measured against the whole suite, the flag's value could be dropped and the run
stayed green — and a gate whose exclusion silently stops working reports violations that
the project has already answered.

**Two of the eight are NOT measured and therefore not judged:** `coupling`'s share filter
and `inventory --under`. They are listed in the finding itself as "not individually
mutated". The only measurement this pass made of them ran against a copy holding
`review.py` alone, without the skill's `references/` and `assets/` — a harness that reddens
every test which assembles a prompt, so its verdicts say nothing. They are named again
under "found, not fixed": each needs one whole-suite mutation run.

**Commit:** `f8007b3`

**The other side:** every new test asserts both directions — the claim at the limit still
imports and `check` accepts it; a valid `risk` still orders the blocks
(`test_order_риск_важнее_частоты`); `next` names the block and then prints nothing when all
are closed; `restamp` on a live file still stamps
(`test_повторный_restamp_находки_ничего_не_пишет`); and `--exclude` frees exactly the hit
that matches it and no other.

---

## T3-008 · low · a test that asserts only the absence of a complaint

**Re-checked:** reproduced — the commit-touches gate silenced for paths with a space
(`and " " not in f["file"]`) left `test_путь_с_пробелом_не_ломает_проверку_коммита` green.

**Done:** the test now proves both sides on a path with a space — a commit that does NOT
touch the file is refused, and the commit that does is accepted with `check` green. The
class behind it is the silent fixture: `Stand.commit` and the stand's own git setup are
checked now, so a fixture that never reached the state it is named for fails instead of
passing quietly.

**Commit:** `18f5770`
**Red on revert:** yes, build ok:

~~~
--- the gate silenced for paths with a space
    RED   test_путь_с_пробелом_не_ломает_проверку_коммита
--- the gate silenced for non-ASCII paths
    RED   test_коммит_не_касающийся_кириллического_файла_по_прежнему_ловится
~~~

The second line is the sibling address of the same class: the non-ASCII direction was
already held by its own test, so the Cyrillic test only gained the assertion that `check`
ends green.

---

## T3-009 · low · the suite's verdict rested on CPython's UTF-8 safety net

**Re-checked:** reproduced. With `PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` in the C locale the
suite is red — and red in a way that names nothing: 195 errors, the first being
`UnicodeEncodeError` from `subprocess` encoding a commit message.

**Done:** `child_env()` is the environment of every child of the suite (UTF-8 mode, UTF-8
IO, a UTF-8 locale). The parent's own encoding cannot be fixed from inside, so the module
refuses to load with a message naming the way out, and CI pins `PYTHONUTF8=1` and the
locale in the workflow.

**Commit:** `18f5770`
**Test:** `TestSuiteRuleTest.test_каждый_потомок_запускается_с_общим_окружением` (the class
rule) and `test_узда_видит_запуск_которого_ещё_нет` (both directions on sources that do not
exist in the suite).
**Red on revert:** a spawn written without `env=child_env(...)` is red by the class rule —
measured on four fixture shapes, including an environment built as `dict(os.environ, …)`.

**The other side:** the rule must not ask for anything of a spawn that is written
correctly: three innocent shapes (a direct call, an environment with an addition, an
environment taken from a variable assigned from `child_env`) pass.

---

## T3-010 · low · the developer's global git config decided the verdict

**Re-checked:** both cells reproduced exactly as the finding describes.

~~~
ignore   RED test_шаблон_по_нетрекнутым_файлам_зовёт_git_add
gpgsign  RED test_origin_по_прежнему_ловит_отставание
gpgsign  RED test_order_ставит_часто_меняющийся_блок_выше_при_равном_риске
~~~

**Done:** `child_env()` sets `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` to the null device
and `GIT_CONFIG_NOSYSTEM=1`, so a child of the suite sees only the config the stand wrote
itself. The stand names its branch explicitly (`git init -b`), so `init.defaultBranch` does
not decide it either. `Stand.commit` is checked, so a commit that cannot happen is named
where it happens instead of six tests away.

**Commit:** `18f5770`
**Re-measured after the fix:**

~~~
ignore   green test_шаблон_по_нетрекнутым_файлам_зовёт_git_add
gpgsign  green test_origin_по_прежнему_ловит_отставание
gpgsign  green test_order_ставит_часто_меняющийся_блок_выше_при_равном_риске
~~~

and the whole suite under a clean runner with no global git config at all (`HOME` empty):
255 tests, OK. The CI step that set a global identity is gone with it.

**The other side:** pinning the config must not narrow what the kit supports — a project
whose main branch is `main` goes through `init`, `coverage`, `set-status` and `check`
unchanged: `GitTruthTest.test_главная_ветка_проекта_ничего_не_решает`.

---

## T3-011 · low · the stub was softer than the real client

**Re-checked:** reproduced — run against the suite's own stub with exit 0, the journal line
was

~~~
hunter — NO RESULT EVENT — the run was killed or the stream is truncated · spend: ? min,
? turns, 0 tool calls, … cost estimate unknown
~~~

and `test_успешный_прогон_записан_обычной_строкой` accepted that as an ordinary completed
run. The shape an operator reads as "the block was hunted" was produced by no test.

**Done:** one source for the stream of a whole run (`stream_text()`), used by the `axes.py`
stubs and by the `claude` stub of `run-role.sh` alike. The success test now asserts the
completed spend line — turns, cost, and the absence of both `NO RESULT EVENT` and
`RUN CUT OFF`; the agent's reply is asserted through `run-role.sh` itself rather than
through `axes.py` on a hand-written file.

**Commit:** `f8007b3`
**Test:** `SpendTest.test_успешный_прогон_записан_обычной_строкой` and
`test_ответ_агента_печатается_из_целого_потока`.
**Red on revert:** yes — the stub back to a stream with no `result` event, build ok:

~~~
RED   test_успешный_прогон_записан_обычной_строкой
~~~

**The other side:** the truncated and the no-result endings must still be told apart from a
completed run, and they are — `test_обрезанный_поток_не_роняет_запуск_роли` and the new
`test_поток_без_события_result_виден_в_дневнике_как_несостоявшийся_замер`, which keeps the
old stub's behaviour under its own name.

---

## T3-012 · low · the NUL rule was blinded by splitting the git prefix out

**Re-checked:** reproduced — `untracked_files` rewritten as
`["git", "-C", str(ROOT)] + ["ls-files", "--others", …]` with `-z` dropped and
`splitlines()` in place of `split("\0")`: the whole suite green.

**Done:** the rule assembles argv per CALL — across `+` concatenation and across a
variable the function builds up with `cmd = [...]` / `cmd += [...]` — and asks `-z` of any
git call whose arguments name a command or flag that prints paths. `grep` joined that set,
and with it the rule found a live defect; see the incidental fix below.

**Commit:** `3720b2a`
**Test:** `SourceRuleTest.test_список_путей_у_git_всегда_запрашивается_NUL_разделённым`
(the tool) and `test_узда_видит_вызов_собранный_по_частям` (three assemblies, both
directions).
**Red on revert:** yes, build ok:

~~~
RED   untracked_files: prefix split out, -z dropped
RED   review_refs without -z
~~~

**The other side:** the same three assemblies WITH `-z` pass, so the rule does not ask
anything of a call that already does the right thing.

---

## T3-013 · low · a name handed to git as a pattern

**Re-checked, and the finding's mechanism is worse than described.** Measured directly:
git matches the pathspec `app/[id]/page.tsx` against the literal path `app/[id]/page.tsx`
AND against `app/i/page.tsx`. So the defect is not that the name matches nothing — it is
that a name that DOES NOT EXIST matches a neighbour:

~~~
'app/[id]/page.tsx'            -> ['app/[id]/page.tsx', 'app/i/page.tsx']
':(literal)app/[id]/page.tsx'  -> ['app/[id]/page.tsx']
'app/[id].tsx'                 -> ['app/i.tsx']          (no such file!)
':(literal)app/[id].tsx'       -> []
~~~

`rule_problem` and `--fixed-in` asked exactly that way, so `--rule app/[i]/page.tsx` was
accepted with no such file in the repository — the guard-exists check, which was written
because "a typo in the path made the class closed without a rule", answered on a
neighbouring file.

**Done:** `named_file()` — one place that asks git whether a NAME is tracked, with
`:(literal)` — and both call sites go through it. A source rule keeps the next name out of
a pathspec: every list literal handed to `git_files`/`index_rows`/`listed`/`untracked_files`
must be a declared pattern or a `:(literal)` name.

**Commit:** `3720b2a`
**Test:** `GitTruthTest.test_имя_файла_со_скобкой_это_имя_а_не_образец` (behaviour, both
directions) and `SourceRuleTest.test_имя_файла_не_уходит_к_git_образцом` (the class).
**Red on revert:** yes, build ok — `named_file` without `:(literal)`:

~~~
RED   test_имя_файла_не_уходит_к_git_образцом
RED   test_имя_файла_со_скобкой_это_имя_а_не_образец  (both --rule and --fixed-in accepted a missing file)
~~~

**The other side:** the real route file is accepted by `--rule` and by `--fixed-in`, it
takes part in the block fingerprint, and editing it turns `check` red — all in the same
test.

**Not killable, and left as it is:** the `:(literal)` in `file_sha` cannot be killed by a
test. The call is followed by an exact-path filter (`r[2] == rel`), so the extra rows a
bracket class brings in are dropped anyway. It stays as defence in depth, and it is now
required by the source rule.

---

## T3-014 · low · the threshold rule read one spelling of an assignment

**Re-checked:** reproduced — `FOO_LIMIT = 6 * 7` and `BAR_MAX, BAZ_MAX = 12, 34` at module
level, with no comment above either, left the suite green.

**Done:** the rule walks every module-level assignment whose targets are upper-case names —
including a tuple of them and an annotated one — and asks for a source whenever a numeric
constant appears ANYWHERE in the value, not only when the value IS one.

**Commit:** `3720b2a`
**Test:** `SourceRuleTest.test_каждое_число_в_коде_названо_и_объяснено` (the tool) and
`test_узда_видит_порог_записанный_не_константой` (both directions on three spellings).
**Red on revert:** yes, build ok — all three spellings added to the real tool with no
comment above them:

~~~
RED   a bare threshold as an expression (FOO_LIMIT = 6 * 7)
RED   a bare pair of thresholds (BAR_MAX, BAZ_MAX = 12, 34)
RED   a bare plain constant (QUX_LIMIT = 42, the rule as it was)
~~~

**The other side:** the same three spellings WITH a comment above pass, and a tuple of
strings is not asked for a source at all.

---

## T3-015 · low · the tool was spawned as PATH `python3`

**Re-checked:** the finding states the matrix cell cannot be produced on this machine —
PATH `python3` and `sys.executable` are the same binary and no second interpreter exists.
Re-checked: still true, so the defect is read in the source, as the finding says.

**Done:** every spawn of the tool uses `sys.executable`, and the class is held by the same
source rule as T3-009: an interpreter taken from PATH is named by the rule together with
the reason. A run under `python3.12` now really measures 3.12.

**Commit:** `18f5770`
**Test:** `TestSuiteRuleTest.test_каждый_потомок_запускается_с_общим_окружением`; the rule
itself is proven by `test_узда_видит_запуск_которого_ещё_нет`, whose fourth offender is a
spawn with `"python3"` as argv[0].
**Red on revert:** the rule flags that fixture; the whole-suite direction cannot be
measured here for the reason above.

---

## Incidental fixes

Each of these was found while fixing a finding of this block, each is a defect of its own
kind, and each has its own test.

**1. `review_refs` parsed `git grep` output as plain text** (`skills/finetooth/scripts/review.py`).
Found by the widened NUL rule of T3-012. Measured:

~~~
git grep -n --full-name -e H1-001    -> b'"\\321\\204\\320\\260\\320\\271\\320\\273 ….ts":1:see H1-001 here'
git grep -z -n --full-name -e H1-001 -> b'файл модуль.ts\x001\x00see H1-001 here'
~~~

A reference in a file with a non-ASCII name reached the operator C-quoted, and a path
containing `:` was cut at the colon — an address that leads nowhere, in the command whose
whole job is to say where the id is named. Fixed with `-z` and NUL-separated fields.
**Test:** `ReviewToolTest.test_refs_называет_не_ASCII_путь_как_он_есть`.
**Red on revert:** yes — `-z` removed, build ok, both that test and the source rule red.

**2. `--fixed-in` accepted a file that does not exist** — the same bracket class as T3-013,
at the address the finding lists as "equally untested". Fixed by `named_file()`.
**Test:** the `--fixed-in` half of `test_имя_файла_со_скобкой_это_имя_а_не_образец`.

**3. The CI workflow no longer sets a global git identity** and pins the locale instead:
the identity is the stand's own business now, and the locale was the cell that was not
pinned. Verified by running the whole suite with `HOME` pointing at an empty directory:
255 tests, OK.

---

## Found, not fixed

Grouped, left to the lead.

**`coupling`'s share filter and `inventory --under` are unmeasured.** Each needs one
whole-suite mutation run against a full copy of the skill (about 200 s apiece). Nothing in
this pass touched either mechanism.

**The group-comment rule of the threshold guard.** A constant added directly under a
commented constant inherits that comment — `# measured: …` above `A = 1` also covers `B = 2`
written under it. That is the documented intent (a comment may stand above a GROUP), but it
means the rule can be satisfied by placement rather than by a source. Widening it to demand
a comment per constant would touch every grouped constant in the tool; the decision is not
a fixer's.

**`git diff --stat` in `summary --aged`** (`review.py`, the diff range printed for a human)
is the one git call left that prints paths without `-z`. It is printed, not parsed, so the
NUL rule does not ask for it — but a non-ASCII path shows up C-quoted in what a human reads.

**`section_body` and the raw-lines exemption.** The quotation rule's `RAW_LINES` set is a
list of names, and the class rule it belongs to is otherwise shape-based. A second function
that hands out raw section lines would have to be added to that set by hand.

**Observations outside the assignment.** The suite now takes ~210 s plus ~25 s for the two
mutation harnesses. The harnesses are the only tests that run the suite recursively; they
are skipped when the suite itself runs against a mutant, and that skip is the only thing
between the guard and an infinite regress. Worth a look if the kit ever gains a second
mutation harness.

---

## Rejected

None. The only thing this pass does not stand behind is the pair of mechanisms inside
T3-007 named above: not rejected, not confirmed — not measured.

---

## What was run

The whole suite, at the end of the series:

~~~
$ python3 -m unittest discover -s tests
...........................................................................
----------------------------------------------------------------------
Ran 277 tests in 292.271s

OK
~~~

277 tests against 248 at the start of the block: 29 new, and 47 rewritten. About 25 s of
that is the two mutation harnesses, which run 63 gates × 2 mutations plus the control.

The suite as a clean CI runner sees it — no global git config at all (`HOME` empty), the
locale pinned as the workflow now pins it:

~~~
$ HOME=<empty> PYTHONUTF8=1 LC_ALL=C.UTF-8 python3 -m unittest discover -s tests
Ran 255 tests in 236.155s
OK
~~~

(255 there: measured before the last two commits added their tests.)

The targeted mutation run for the mechanisms outside `cmd_check` — each mechanism broken in
a full copy of the skill, only the test named for it run against that copy, and a control
run on an untouched copy right after:

~~~
RED   cmd_next: the whole body           killed by: test_next_называет_следующий_незакрытый_блок
green     control (untouched copy)
RED   backfill: the early return         killed by: test_повторный_backfill_на_проставленном_состоянии_ничего_не_пишет
green     control (untouched copy)
RED   restamp_finding: the refusal       killed by: test_restamp_на_пропавшем_файле_отказ_а_не_отпечаток_пустоты
green     control (untouched copy)
RED   set-finding: write inside the loop killed by: test_set_finding_на_нескольких_номерах_всё_или_ничего
green     control (untouched copy)
RED   import: the claim cap              killed by: test_импорт_держит_те_же_потолки_что_и_проверка
green     control (untouched copy)
RED   block_risk: the refusal            killed by: test_риск_вне_словаря_это_отказ_а_не_трейсбек
green     control (untouched copy)
RED   guard-grep: --exclude loses its value  killed by: test_исключение_снимает_попадание_а_остальные_оставляет
green     control (the script restored)
~~~

`import`'s claim cap and `block_risk`'s refusal were also measured against the WHOLE suite
(201 s and 199 s): each is killed by the test named for it and by nothing else.

**`skills-ref validate skills/finetooth` was not run: the validator is not installed in
this environment** (CI installs it into a venv from git). The series adds and removes no
file in `skills/` — the only change there is 23 lines in `scripts/review.py` — so the
skill's shape is untouched, and `SkillFormatTest`, which repeats part of the validator's
rules, is green inside the run above. The gate still has to run in CI.

## The state check

`check` is red on the state of the review as a whole, and every red line belongs to another
block: open findings of T1, T2 and T4 whose files this series touched (`review.py`,
`tests/test_review.py`, the workflow, the changelog) now carry a stale code fingerprint, and
three roots of T2 and T4 still have no guard. No finding of T3 is among them.

`T3: block files changed after the review` is expected and is left alone deliberately: the
fixer's own edits are what changed those files, and `restamp` says "the new text was seen",
which is the fix reviewer's statement to make, not the fixer's.
