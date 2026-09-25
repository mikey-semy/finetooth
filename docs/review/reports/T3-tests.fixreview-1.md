# T3 — fix review, round 1

15 findings closed by the fixer, all 15 re-checked by mutation here. Four findings of my own:
2 medium, 2 low. Another round is needed, and the reason is in the last section — the two
mediums are the same class as the root the block was filed against, one level up.

## What was checked and how

The diff of `f1a44a0..HEAD` read in full: four fix commits plus the report commit, 23 lines
of `skills/finetooth/scripts/review.py` and ~1450 lines of `tests/test_review.py`.

**Baseline.** The suite on this machine, unmutated:

~~~
Ran 277 tests in 294.838s
OK
~~~

which matches the fixer's report (277 tests).

**Method.** A copy of the whole tree outside the repository; each mechanism broken in the
copy, the named test run against it, the copy restored. Every mutant was checked to parse
before its verdict was read. Where the fixer's claim was about the WHOLE suite (a survivor),
the whole suite was run, not the named test alone.

**Every fix proven by reverting.** Each mechanism the report names was broken in the copy
and the test named beside it run against it. All mutants parsed before their verdict was
read; the ones that did not (three malformed edits of mine) were rewritten and re-run rather
than counted.

| what was broken | test run | verdict |
|---|---|---|
| a `GATES` entry re-pointed at an unrelated test (`: no manifest` → `test_описание_в_пределах`) | `GateMutationTest` | **RED** (T3-003) |
| a gate test weakened back to `assertIn(msg, out.stdout)` | `test_названный_тест_краснеет_когда_ворота_сменили_строгость` | **RED** (T3-001) |
| a new gate written `problems += […]` | `GateRegistryTest` | **RED** (T3-002) |
| a new gate written `problems.extend([…])` | `GateRegistryTest` | **RED** (T3-002) |
| a new gate written `problems = problems + […]` | `GateRegistryTest` | **RED** (T3-002) |
| a new gate written `problems.insert(0, …)` (unknown spelling) | `GateRegistryTest` | **RED** (T3-002) |
| `backfill`'s early return on a clean state | `test_повторный_backfill_…_ничего_не_пишет` | **RED** (T3-004) |
| `set-finding`'s register write moved inside the id loop | `test_set_finding_на_нескольких_номерах_всё_или_ничего` | **RED** (T3-004) |
| a new subcommand with no `ARGV` entry | `test_ни_одна_команда_не_роняет_трейсбек_…` | **RED** (T3-005) |
| `cmd_sizes` raising on a hand-written definition | `test_ни_одна_команда_не_роняет_трейсбек_…` | **RED** (T3-005) |
| `MSG["ru"]["refs_cut"]` deleted | `test_обе_языковые_таблицы_держат_одни_ключи_и_подстановки` | **RED** (T3-006) |
| a substitution field renamed in the ru table only (`{cli}` → `{command}`) | `test_обе_языковые_таблицы_держат_одни_ключи_и_подстановки` | **RED** (T3-006) |
| `references/hunter.ru.md` removed | `test_у_каждого_шаблона_и_образца_есть_второй_язык` | **RED** (T3-006) |
| `import`'s claim cap dropped | `test_импорт_держит_те_же_потолки_что_и_проверка` | **RED** (T3-007) |
| `block_risk`'s refusal dropped | `test_риск_вне_словаря_это_отказ_а_не_трейсбек` | **RED** (T3-007) |
| `review_lang`'s fallback dropped | `test_язык_которого_нет_не_роняет_инструмент` | **RED** (T3-007) |
| `cmd_next`'s body broken | `test_next_называет_следующий_незакрытый_блок` | **RED** (T3-007) |
| `restamp`'s refusal on a vanished file dropped | `test_restamp_на_пропавшем_файле_…` | **RED** (T3-007) |
| `guard-grep --exclude` loses its value | `test_исключение_снимает_попадание_а_остальные_оставляет` | **RED** (T3-007) |
| the commit-touches gate silenced for paths with a space | `test_путь_с_пробелом_не_ломает_проверку_коммита` | **RED** (T3-008) |
| a `subprocess.run` written without `env=child_env()` | `test_каждый_потомок_запускается_с_общим_окружением` | **RED** (T3-009) |
| the `claude` stub back to a stream with no `result` | `test_успешный_прогон_записан_обычной_строкой` | **RED** (T3-011) |
| `untracked_files` with the prefix in a **variable** and `-z` dropped | the whole suite | **GREEN — R1-001** |
| `named_file` without `:(literal)` | `test_имя_файла_со_скобкой_…`, `test_имя_файла_не_уходит_к_git_образцом` | **RED** (T3-013) |
| `review_refs` without `-z` | `test_refs_называет_не_ASCII_путь_как_он_есть`, the NUL rule | **RED** (incidental 1) |
| a bare `FOO_LIMIT = 6 * 1000` / `BAR_MAX, BAZ_MAX = 12, 34` | `test_каждое_число_в_коде_названо_и_объяснено` | **RED** (T3-014) |
| a gate moved into a module-level helper of `cmd_check` | `GateRegistryTest`, then the whole suite | **GREEN — R1-002** |

**Gates checked by violation, not by reading.** The repository's gates here are the suite
itself and its class rules. Each rule was fed synthetic sources through its own function —
`_nul_offenders`, `_name_as_pattern`, `_spawns`, `_bare_numbers`, `_check_gates` — so that a
verdict is about the rule's shape, not about what happens to be written in the tool today.

**Reproduced live.** `git grep` with and without `-z` measured against real git on a
throwaway repository with a path holding both non-ASCII characters and a colon; the twelve
real `claude` event streams in `$TMPDIR/finetooth-runs` read and compared with the new stub;
the suite run under a hostile environment.

**Environment matrix, run here.**

| cell | result |
|---|---|
| this machine, as the developer has it (Python 3.14.7) | `Ran 277 tests in 294.838s` OK |
| a copy of the tree with `.git` deleted | `Ran 277 tests in 293.121s` OK |
| `HOME` with a hostile global git config — `commit.gpgsign=true` and `tag.gpgsign=true` with no key, `core.excludesFile` holding `vendor/`, `init.defaultBranch=main` — **and** `LC_ALL=C LANG=C` with `PYTHONUTF8` unset | `Ran 277 tests in 289.013s` OK |
| `LC_ALL=C LANG=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` (the safety net off) | one import-time refusal naming the fix, not 195 errors — see R1-003 |
| Python 3.12 | not producible: 3.14.7 is the only interpreter here, as T3-015 records |

The third row is the one that matters: every cell the finding named as a live failure
(`gpgsign` reddening six tests, `excludesFile` reddening one, the branch name, the locale)
is green at once, and `git init -b` plus `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` in
`child_env()` are what makes it so.

**Not done.** `skills-ref validate` was not run here either — the validator is not installed
and the fixer's argument stands on inspection: this series adds and removes no file under
`skills/`, and `SKILL.md`, `references/` and `assets/` are untouched, so the shape the
validator checks cannot have changed. Python 3.12/3.14 remains one cell, not two: 3.14.7 is
the only interpreter on this machine, exactly as T3-015 records.

## Findings

### R1-001 · medium · the widened NUL rule is blind to the very refactor its finding named: the prefix in a VARIABLE
**Location:** `tests/test_review.py:4906` (`SourceRuleTest._nul_offenders`)
**What is wrong:** T3-012 was closed by teaching the rule to assemble argv "per call, across
concatenation and across a variable built up in steps". It does two of the three shapes.
`strings()` folds `ast.BinOp` by recursing into both sides, and `kept` resolves a plain
`ast.Name` argv — but nothing resolves a Name that appears *inside* a BinOp. So
`GIT + ["ls-files", …]`, where `GIT` holds the hoisted `["git", "-C", str(ROOT)]` prefix,
yields items without `"git"` at all, and the call is skipped before `-z` is ever asked for.
**Failure scenario:** measured on the current tree. `untracked_files` rewritten as the
obvious refactor —

~~~python
GIT = ["git", "-C", str(ROOT)]

def untracked_files(specs: list[str]) -> list[str]:
    out = subprocess.run(GIT + ["ls-files", "--others", "--exclude-standard", "--", *specs],
                         capture_output=True, text=True, check=False).stdout
    return [f for f in out.splitlines() if f]
~~~

— with `-z` dropped and `splitlines()` in place of `split("\0")`. The mutant compiles; the
named rule test is green; **the whole suite is green: `Ran 277 tests in 293.121s / OK`.**
A non-ASCII untracked path then reaches `check` C-quoted and matches nothing — the exact
consequence T3-012 records, still reachable with the suite green. The only behaviour test of
`untracked_files` (`test_шаблон_по_нетрекнутым_файлам_зовёт_git_add`) uses the ASCII path
`vendor/tool.py`, so it cannot see the difference; the class rule is the whole guard.
Fed synthetic sources directly, the rule answers:

| how argv is assembled | rule sees it |
|---|---|
| `["git", "-C", R, "ls-files", …]` one literal | yes |
| `["git", "-C", R] + ["ls-files", …]` two literals | yes |
| `cmd = ["git", "-C", R]; cmd += ["ls-files"]; run(cmd)` | yes |
| `G = ["git", "-C", R]` … `run(G + ["ls-files", …])` | **no** |
| `g = ["git", "-C", R]` inside the function, `run(g + […])` | **no** |
| `run([*G, "ls-files", …])` | **no** |

The last shape matters twice over: the tool already writes `*specs` inside these very
literals, so star-unpacking a prefix is the same idiom it uses today.

**Why it is a defect:** invariant 5 (paths are handled NUL-separated) and invariant 2 (a
check whose mechanism can be disabled while the suite stays green is untested). The fixer's
report states the rule assembles argv "across a variable" — it does so only when the whole
argv *is* that variable.

**The same one-line habit in the sibling rule written in the same commit.**
`SourceRuleTest._name_as_pattern` (T3-013's class guard) only inspects calls whose first
argument is an `ast.List` literal: `git_files([rel])` is caught, while `want = [rel];
git_files(want)`, `git_files(["--"] + [rel])` and `git_files((rel,))` all return `[]`.
That one has less consequence today — the behaviour test
`test_имя_файла_со_скобкой_это_имя_а_не_образец` covers the two live call sites — but it is
the same blind spot in the same class of guard.
**Introduced by this round or present before:** the blind spot is new — this shape of the
rule was written in `3720b2a`. The underlying defect (T3-012) is older.
**Confidence:** confirmed

### R1-002 · medium · the gate registry still cannot see a gate that lives in a helper — the other half of T3-002's own scenario
**Location:** `tests/test_review.py:4416` (`_check_gates`), `tests/test_review.py:4473`
(`_refuse_unknown_spelling`)
**What is wrong:** T3-002's scenario is "splitting a 500-line `cmd_check` with extend, the
obvious refactor, therefore drops gates out of the registry silently". The fix read the
*second* half of that sentence — the spellings — and not the first. `_check_gates` still
takes `fn = next(n for n in ast.walk(tree) if … n.name == "cmd_check")` and walks that one
function; `_refuse_unknown_spelling`, the new loud failure, is likewise called only for
statements inside it. A part of `cmd_check` moved into a module-level helper that takes
`problems` and appends to it is invisible to both.
**Failure scenario:** measured on the current tree. A gate written the way a split of
`cmd_check` writes it —

~~~python
def _reserved_role_gate(defn, problems) -> None:
    """Part of `cmd_check`, split out — the obvious next refactor."""
    for b in defn["blocks"]:
        if b.get("role") == "__never__":
            problems.append(f"{b['id']}: role `__never__` is reserved")


def cmd_check(args) -> int:
    ...
    _reserved_role_gate(defn, problems)
~~~

— produces no registry key, raises no `UnknownGateSpelling`, and needs neither a `GATES`
entry nor a test. Measured: `GateRegistryTest` green (`Ran 6 tests`, OK), and **the whole
suite green: `Ran 277 tests in 294.852s / OK`.** The gate can then be deleted later with the
suite still green — invariant 2's exact failure, and the one T3-002 was filed to stop.
The four spellings the fix *did* close were re-measured and all four are caught: `+=`,
`.extend`, `problems = problems + […]` and the unknown `.insert` each redden
`GateRegistryTest`.
**Why it is a defect:** invariant 2 — a check whose mechanism can be disabled while the
suite stays green is untested. The register records T3-002 as `fixed` against a scenario
that still reproduces.
**Introduced by this round or present before:** the blind spot is older than the round (the
registry always walked only `cmd_check`), but T3-002 was closed against it, so it is a fix
that did not reach its own stated address.
**Confidence:** confirmed

### R1-003 · low · the module-level locale refusal is unreadable in the locale it exists for
**Location:** `tests/test_review.py:37-45`
**What is wrong:** T3-009's fix makes the module refuse to import when the filesystem
encoding is not UTF-8, "so that one refusal names the cause". The message is written in
Russian, and the environment it fires in is exactly the one that cannot print Russian:
`sys.stderr` falls back to `backslashreplace`, so the operator gets a wall of escapes.
**Failure scenario:** measured on the current tree:

~~~
$ LC_ALL=C LANG=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 python3 -m unittest discover -s tests
ERROR: test_review (unittest.loader._FailedTest.test_review)
RuntimeError: кодировка файловой … ascii, … `PYTHONUTF8=1 python3 -m unittest discover -s tests`
Ran 1 test in 0.000s
FAILED (errors=1)
~~~

**Why it is a defect:** invariant 3 — a refusal is read by someone seeing it for the first
time. It is a partial one: the fix command at the end is ASCII and does survive legibly, and
one error beats the 195 the finding measured, so this is a degradation, not a regression.
**Introduced by this round or present before:** introduced by this round (`18f5770`).
**Confidence:** confirmed

### R1-004 · low · a new class guard over the repository itself, named nowhere
**Location:** `tests/test_review.py:5191` (`SourceRuleTest._rules_without_samples`, with
`test_у_каждого_правила_по_исходнику_есть_выдуманный_образец` at 5219 and
`test_узда_видит_правило_которое_никто_не_кормил` at 5240), and `tests/test_review.py:5129`
(`test_узда_видит_свой_разбор_записей_которого_ещё_нет`)
**What is wrong:** this series adds a *fourth* class guard that no finding of T3 asked for:
every source-level rule in the suite must now live in its own function (not inline in a
test) and must be fed at least one invented source besides the tool's own. It is a standing
rule for everyone who touches this file, and it reddened two rules that were already written
(the `git log` marker rule and the language-table check), which is why both were refactored
in this diff. **The commit message of `f8007b3` does describe it, fully and well** — that
part of rule 6 is met. What is missing is the two documents a reader is pointed at:
`T3-tests.fix.md`'s "Incidental fixes" section lists three items and not this one, and the
T3 paragraph of `CHANGELOG.md`/`CHANGELOG.ru.md` says "three class guards were blind…" when
four guards changed and a fifth is new. `grep` for `_rules_without_samples`, either test
name, `RULE_SHAPES` or `SOURCE_MARKS` across the report and both changelogs returns nothing.
**Failure scenario:** a contributor adds a source rule the way this file did it until
yesterday — `for n in ast.walk(ast.parse(self.SOURCE))` inside the test — and the suite goes
red with "правило по исходнику написано прямо в тесте: вынесите его в функцию". The
changelog entry for the release that introduced the rule does not mention it, and neither
does the fix report of the block; they have to find `f8007b3` by `git log -S` to learn where
the rule came from.
**Why it is a defect:** AGENTS.md rule 2's tradition — what a change gates is listed by name
in the CHANGELOG — and rule 6 of this assignment as it applies to the report. The guard
itself is sound and has both directions; the gap is that the public record of this release
undercounts what it started enforcing.
**Introduced by this round or present before:** introduced by this round (`f8007b3`, with
the log-mark sample following in `3720b2a`).
**Confidence:** confirmed

## Checked and found correct

**The `refused()` / `warned()` split is sound.** `check` prints WARNINGS first and
CHECK FAILED second (`review.py:3377-3387`), so `refused()` — everything after
`CHECK FAILED:`, and only when the exit code is 1 — cannot contain a warning, and
`warned()` — everything after the warnings header, and only when the exit code is 0 —
returns `""` the moment any refusal fires. A gate moved to `warnings` therefore cannot
satisfy `refused()`, and a warning promoted to a refusal cannot satisfy `warned()`. That is
the mechanism T3-001 was missing, and it holds in both directions.

**`review_refs -z` is right, and the measurement behind it reproduces.** Measured on a
throwaway repository with a file named `src/модуль:раз.ts`:

~~~
git grep -n  …  -> b'"src/\\320\\274\\320\\276\\320\\264…:\\321\\200\\320\\260\\320\\267.ts":1:…'
git grep -z -n  …  -> b'src/модуль:раз.ts\x001\x00// see H1-001 here\n'
~~~

`path NUL line NUL text`, one record per line — exactly what the new parse expects. Both the
C-quoting and the colon truncation are real, and both are gone.

**`named_file()` reaches every address of T3-013.** There are three places where a *name*
can meet git-pathspec: `file_sha` (already had `:(literal)`, and the exact-path filter
`r[2] == rel` right after it is why no test can kill it — the fixer says so and it is true),
`rule_problem` and `--fixed-in`. The fourth candidate, the "file is not in the repository"
gate at `review.py:2995`, compares against the `tracked` set by membership, never as a
pathspec, so it was never affected. Every `rule` and `fixed_in` value already in
`findings.jsonl` is a plain name, and both role templates say "path to the guard" — so
narrowing to `:(literal)` breaks nothing recorded and demands nothing new of an agent
(invariant 9 needs no prompt change here).

**The mutation harness is honest about what counts as a kill.** Its pass condition is the
child run's own failure, fenced by `assertIn("Ran 1 test")`: a mutant that broke the module
would give "Ran 0 tests" and be reported as a complaint rather than counted as a kill, and
`test_на_целой_копии_все_названные_тесты_зелены` is the control for the copy itself. The 63
registry keys are unique; one test covers two of them, and the harness requires it to go red
for each separately.

**The `claude` stub is no softer than the real client on what `axes.py` reads.** Twelve real
captures in `$TMPDIR/finetooth-runs` inspected: ten carry exactly one `result` event (the two
with two are the resumed runs the journal itself records), and the fields the stub emits —
`subtype`, `num_turns`, `duration_ms`, `total_cost_usd`, `usage.output_tokens`, `result` —
are all present in the real ones. The stub omits `system`/`user`/`tool_progress` events, as
it did before this round; nothing the tests assert depends on them.

**No test depends on the kit being a git repository.** The whole suite ran green (277 OK) in
a copy of the tree with `.git` removed — which is also the harness this review's mutations
ran in. That is a second, unplanned answer to the block's hypothesis 3: the suite does not
read the kit's own `docs/review/` state either.

**The commit attributions in the report's finding table are right.** `git log -S` puts
`GateMutationTest` and `refused()` in `a6d7df3`, `child_env()` in `18f5770` and
`named_file()` in `3720b2a` — each where the table says. (`f8007b3`'s commit message
re-summarises `GateMutationTest` as part of the series narrative; the code is not there.)

**T3-015 holds for the suite.** No `subprocess` call in `tests/test_review.py` spawns the
tool as PATH `python3` any more; the only remaining occurrences are expected-output
assertions and the rule's own offending fixture. (`run-role.sh` still calls `python3` for
`axes.py`, correctly: it is a shipped bash asset with no `sys.executable` to reach for.)

**Every guard named by a closed finding still exists.** All eight `rule` values in the
register (`GateRegistryTest`, `GateMutationTest`, `SourceRuleTest`, `HandWrittenInputTest`,
`ReportShapeTest`, and three named tests) resolve to classes and tests present in the tree
after this series.

**Not a finding, worth a line:** the report's Commits table names `44b884c` for the report
commit; the commit in the branch is `f308790`. The four fix commits it names all exist and
match the `fix_commit` fields in the register.

## Is another round needed

**Yes — two medium findings, and both are of the kind rule 11 names: a fix that did not
reach an address of its own defect.**

But the number is not the point, so first what got better, because a great deal did.

The block's heaviest class is genuinely closed. Before this series a gate of `check` could
be moved from the refusals to the warnings and the whole suite stayed green — `check`
printed the same sentence and exited 0 on a state it had refused — for 47 of the 63 gates,
by the fixer's count, which I did not re-measure on the old code.
Measured here on the new: weakening a single gate test back to `assertIn(message, out.stdout)` reddens
`test_названный_тест_краснеет_когда_ворота_сменили_строгость`, and re-pointing a registry
entry at an unrelated test reddens `GateMutationTest`. The registry no longer asserts that a
test *exists*; it asserts that the test *dies with the gate*, twice over, for every gate, and
it is fenced by a control run that stops "the copy is broken" from reading as "the gate is
held". That is the difference between a list and a measurement, and it is the right shape.

Everything else the report claims was re-measured and holds. Of the 27 mutations run here,
25 were killed by the test named beside them; only the two written up above survived. Killed:
`import`'s claim cap, `block_risk`, `review_lang`, `cmd_next`, `restamp`, `backfill`'s
idempotence, `set-finding`'s all-or-nothing, `guard-grep --exclude`, the commit-touches gate
on a path with a space, the argparse guard in both directions, the two language tables (a
deleted key, a renamed substitution, a removed `.ru.md`), and the stub that was softer than
the real client. Two real product defects were found and fixed along the
way, both correctly and both named in the report: `review_refs` handing the operator a
C-quoted path truncated at a colon, and `--fixed-in` accepting a file that does not exist.
The suite's verdict no longer depends on the developer's global git config or on CPython's
UTF-8 safety net. Nothing in the diff is bloat: `review.py` moved 23 lines, all of them
load-bearing.

**What did not break.** No regression was found in the tool's behaviour, no test was found
green for the wrong reason, no fake was found softer than the thing it stands for, and no
fix was found to have been claimed and not written. The report's account of itself is honest
down to naming the two mechanisms it left unmeasured.

**The count, and the pattern in it.** Four findings: 2 medium, 2 low. **All four sit inside
the code this round changed** — R1-001 in the rule widened in `3720b2a`, R1-004 in the guard
added in `f8007b3`, R1-003 in the refusal written in `18f5770`, R1-002 in `_check_gates` as
`a6d7df3` rewrote it. None is
a defect in the tool the kit ships; all four are about the gate that guards it.

**And the pattern is the same one the block was filed for.** The hunter recorded a root with
three instances — *"class guard keyed on incidental syntax"* (T3-002, T3-012, T3-014). The
fix widened each of those three guards to the next spelling. Both mediums above say that the
widened guards are, again, keyed on incidental syntax: the NUL rule folds `[…] + […]` but
not `G + […]` or `[*G, …]`; the registry reads four ways of appending but still only inside
one function. This is the second pass in a row where the top finding is in that one class,
and it will be the third if the answer is "widen the pattern again" — there is always
another spelling.

**So: one more round, and then a human decides the mechanism.** The round is worth running,
because R1-001 and R1-002 are each a few lines and their tests already exist in shape. But
the standing instruction to the fixer of round 2 should be: do not close them by adding two
more `isinstance` branches. The class wants a different kind of guard — the rules run against
deliberately mutated sources the way `GateMutationTest` runs the gates, or the argv checked
where it is actually built rather than where it is written. Choosing between those is not a
fixer's call, and after two rounds in one class it is not another round's either.
