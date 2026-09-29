# T1 — fix report: the tool (review.py, axes.py, run-role.sh, guard-grep.sh)

24 findings, all re-checked against the current code before being touched, all closed.
None rejected. Three defect classes reached three instances or more and are closed by
guards, not by lists of fixed places.

Every fix was proven by mutation: the fix reverted in a copy of the kit, the named test
run against it, and both the build result and the test result read. The two harness runs
are quoted at the end.

**How to read the table.** "Red on revert" means the mutation described in the row turned
the named test red while the mutated copy still compiled — a test that also passes on the
old code guards nothing, and a build that fails proves nothing either.

**A note on this file.** It is `*.fix.md`, so the tool parses it for hypothesis verdicts
like any other report of the block. Written first, its quoted reproductions closed three
hypotheses by accident — the very defect T1-001 is about, in the report that closes it.
They are inside fenced blocks now, and `verdicts_in` on this file returns nothing.

## Commits

| commit | what is in it |
|---|---|
| `242f88b` | Report parsing: a verdict is content, not shape |
| `83a41c1` | git is the source of file truth, and paths travel NUL-separated |
| `79aa8d6` | What a human edits by hand gets a refusal, not a traceback — and a re-run changes nothing |
| `936e621` | The freshness gate says when it cannot run |
| `e6d52b2` | Thresholds that hold at the edge of their range, and every number with its source |
| `3230faa` | A cut-off run is recorded as cut off |
| `e479137` | guard-grep: one marker frees one call, and a missing path is a refusal |
| `7b55f5c` | Every gate of `check` under a test, and three guards to keep the classes closed |
| `2ce050d` | 0.8.0: the review of the tool itself, in the changelog |
| `f90c68d` | The rule about where a verdict is written is held by a test |

One more commit carries the bookkeeping: this report, the register (every finding moved to
`fixed` with its commit and its guard) and a two-line correction to the `commit_file_sets`
docstring, whose measured numbers moved with the commits of this very series (41/9 → 42/10).

---

## T1-001 · high · verdicts inside a fenced block

**Re-checked:** reproduced on the current code — a report whose Hypotheses section answers
nothing and quotes the template's skeleton inside a fenced markdown block gave

~~~
{'T1.1': ['checked'], 'T1.2': ['not checked'], 'T1.3': ['not applicable']}
~~~

**Done:** fence detection now lives in one place, `fenced_lines()`, and `verdict_mentions`
skips every line inside a fence — for verdicts, for the heading tracking and for the table
tracking alike. The same helper replaced the three private fence trackers in `demote`,
`section_body` and `section_items_full` (see T1-004).

Invariant 9 — a change to a mechanism is a change to a prompt: `references/hunter.md`,
`hunter.ru.md`, `verify.md` and `verify.ru.md` now say that a verdict is an ordinary line
of the report, outside code blocks, and that the three example lines above do not count if
copied across as they stand.

**Commit:** `242f88b` (templates), `f90c68d` (the test that keeps the sentence there)
**Test:** `ReportShapeTest.test_вердикт_внутри_ограды_кода_не_вердикт` (forbidden), and
`test_вердикт_вне_ограды_по_прежнему_вердикт` (allowed: a verdict outside a fence still
closes the hypothesis, and a fenced example next to it raises no verdict conflict)
**Red on revert:** yes — fence skip removed (`if fenced:` → `if False:`), build ok, test red.

---

## T1-002 · medium · a headerless numbered table read as verdicts

**Re-checked:** reproduced — a headerless `| 1 | … | confirmed |` table gave the verdicts
below, while the same table with a header gave nothing:

~~~
{'T1.1': ['checked'], 'T1.2': ['not checked']}
~~~

**Done:** a table is a table of hypothesis verdicts only where it says so — its first row
names hypotheses — or inside the "Hypotheses" section, where the row number IS the
hypothesis number. The `or first.isdigit()` branch that made every numbered table a verdict
table is gone.

**Commit:** `242f88b`
**Test:** `ReportShapeTest.test_нумерованная_таблица_вне_раздела_гипотез_не_вердикт`
(forbidden: the second hypothesis, about which the report says nothing, is now NO VERDICT
and `check` demands it), and `test_таблица_названная_гипотезами_по_прежнему_читается`
(allowed). The headerless-table-under-Hypotheses form is held by the existing
`test_оговорка_в_строке_не_переворачивает_вердикт`, whose table moved under that heading.
**Red on revert:** yes — the `isdigit()` branch restored, build ok, test red.

---

## T1-003 · medium · a vocabulary word inside a code span

**Re-checked:** reproduced on all four lines of the verifier's matrix.

**Done:** a code span whose whole content is a vocabulary word is a quotation of the word,
not a verdict (`unquote_verdicts`). A span carrying a whole clause is prose in monospace and
still counts — that is how a live report writes a verdict, this review's own verifier report
included.

**Commit:** `242f88b`
**Test:** `ReportShapeTest.test_слово_вердикта_в_обратных_кавычках_цитата` and
`test_путь_с_n_a_в_кавычках_не_делает_гипотезу_неприменимой` (forbidden);
`test_вся_строка_вердикта_в_кавычках_остаётся_вердиктом` (allowed — the shape the verify
report of this very block uses on every line).
**Red on revert:** yes — `unquote_verdicts` bypassed, build ok, both tests red.

**One half of this finding is not closed, and deliberately.** The verifier folded into it
row 11 of its matrix: `- Z9.9 — the block moves to verified after the report` scores
**checked** on the bare word "verified", with no code span involved, and the expected
verdict is recorded there as "none". That expectation cannot be met without breaking row 22
of the same matrix — `- Z9.16 — verified against production`, expected **checked**. The two
lines are the same shape: a hypothesis id, a dash, a sentence containing "verified". No
mechanical rule separates them; only meaning does. The parser is deliberately lenient about
the live language of reports (the vocabulary carries "refuted", "не подтвердилась",
"unverified"), and narrowing it to a fixed verdict position would refuse honest reports —
the failure the invariants weigh heavier than the leak, because a leak is caught at review
and a refused honest report is discovered by the person whose work it rejects.

Measured after the fix, against the verifier's matrix: rows 9, 25, 26, 28 and 29 now answer
exactly as expected. Rows 10 and 20 — the two lines that quote a verdict word and mean the
opposite — no longer produce a wrong verdict; they produce none at all, which leaves the
hypothesis unanswered and `check` red, the safe direction. Row 11 still answers "checked".
Recorded here rather than papered over.

---

## T1-004 · medium · a `~~~` fence invisible to the parsers

**Re-checked:** reproduced — a manifest listing four hypotheses with a `~~~markdown` block
between the second and the third gave `['T1.1', 'T1.2']`.

**Done:** `FENCE`/`fenced_lines()` recognise both ``` and `~~~` (three or more marks, up to
three spaces of indent, closing fence of the same character with no info string), and
`demote`, `section_body`, `section_items_full` and `verdict_mentions` all call it. The
class is closed structurally: there is no second fence detector left, and a guard keeps it
that way.

**Commit:** `242f88b`
**Test:** `ReportShapeTest.test_тильда_ограда_в_манифесте_не_обрывает_гипотезы` and
`test_заголовок_внутри_тильда_ограды_не_понижается_в_промпте`
**Red on revert:** yes — `~~~` dropped from the fence pattern, build ok, both tests red.

---

## T1-005 · medium · the fingerprint and the line count read the disk

**Re-checked:** reproduced in a scratch repository. With the file laid out,
`block_sha 39e5ec616075aaa3`, `block_lines (3, 6)`; after `rm src/api.ts` with the index
untouched, `file_sha` → `None`, `block_sha 36beab941190364a`, `block_lines (3, 3)`.

**Done:** `file_sha` takes the working tree while the file is laid out there (that is the
text a human and an agent read) and the INDEX when it is not — including the symlink case,
hashed the same way in both branches so the fingerprint does not jump when a sparse
checkout lays the link out. `block_lines` stopped counting by itself and counts through
`file_lines`, which already reads the index and already knows a binary file is not lines.

**Commit:** `83a41c1`
**Test:** `GitTruthTest.test_файл_из_индекса_не_выложенный_на_диск_даёт_отпечаток_и_строки`
— in both directions: removing the file from disk changes neither the line count nor the
verdict of `check`, and a real edit to its contents still turns "block files changed after
the review" red.
**Red on revert:** yes — index fallback replaced by `return None`, build ok, test red.

---

## T1-006 · medium · the fix-commit gate against a quoted path

**Re-checked:** reproduced — `git show --name-only` prints
`"src/\320\274\320\276\320\264\321\203\320\273\321\214.ts"`, and `check` reported
"commit … does not touch src/модуль.ts" for ever while the path with a space passed.

**Done:** the gate reads `git show --name-only -z` and compares raw NUL-separated paths,
the way `ls-files -z` reports them.

**Commit:** `83a41c1`
**Test:** `GitTruthTest.test_находка_на_пути_с_кириллицей_закрывается_коммитом` (allowed:
a truthful fix on a Cyrillic path and on a path with a space now passes) and
`test_коммит_не_касающийся_кириллического_файла_по_прежнему_ловится` (forbidden: a commit
that does not touch the file is still caught — the direction that matters, since a gate
fixed into silence is worse than a gate that nags).
**Red on revert:** yes — `-z` removed, build ok, the first test red.

---

## T1-007 · medium · twenty-four gates of `check` with no test

**Re-checked:** the verifier's measurement reproduced: the gates it names could be silenced
with `python3 -m unittest discover -s tests` still green.

**Done:** a test for every one of them (`GateCoverageTest`, 28 tests), and then the whole
gate inventory of `cmd_check` — all **62** `problems.append` / `warnings.append` sites,
including the ones that were already covered — was re-measured by mutation, one gate per
mutant, each against the test that claims to cover it.

A list of tested places does not survive the next gate somebody adds, so the class is closed
by a rule: `GateRegistryTest` holds the gate → test table in code, extracts the gate
inventory from the source with `ast`, and fails the suite when a gate has no entry or an
entry names a test that does not exist.

**Commit:** `7b55f5c`
**Test:** `GateCoverageTest` (one per gate) + `GateRegistryTest` (the rule)
**Red on revert:** yes, 62 of 62 — the full run is quoted at the end of this report; every
mutated copy compiled, and every gate's test went red. The registry rule was checked the
same way: a new unregistered `problems.append` and an entry naming a nonexistent test each
turn `GateRegistryTest` red.

---

## T1-008 · medium · a missing scan path exits 0

**Re-checked:** reproduced — after `mv internal/billing internal/payments` the same command
printed nothing and exited 0.

**Done:** every path is checked before the scan; a missing one is a refusal (exit 2) that
says the gate scanned nothing, that this is not the same as a clean tree, and what to do
with the gate that calls it. The header's promise ("a path that does not exist is simply
skipped") was the documentation of the defect and is corrected.

**Commit:** `e479137`
**Test:** `GuardGrepTest.test_переименованный_пакет_роняет_ворота_а_не_молчит` — the same
package before and after the rename: exit 1 with the violation, then exit 2 with the
refusal.
**Red on revert:** yes — the existence check disabled, test red.

---

## T1-009 · medium · import assigns an id that already exists

**Re-checked:** reproduced — the register held two `H1-001`, `check` said "duplicate id"
and named no way out, `set-finding` moved only the first.

**Done:** a number is taken from the free ones — never from the count of rows, and never one
that a record of this block already carries, so an id already quoted in the journal or in a
commit message cannot move to another defect. A draft carrying one id twice is refused with
the way out named.

**Commit:** `79aa8d6`
**Test:** `IdempotenceTest.test_импорт_не_выдаёт_занятый_номер` (forbidden: no collision,
and `H1-001` still means the finding it always meant),
`test_повторный_импорт_того_же_файла_ничего_не_добавляет` (allowed: the re-import is still a
no-op), `test_две_строки_с_одним_номером_в_черновике_отказ`
**Red on revert:** yes — positional numbering restored → the first two red; the duplicate
refusal disabled → the third red. Both copies compiled.

---

## T1-010 · medium · a hand-written block definition is never validated

**Re-checked:** reproduced on `status`, `order`, `summary` and `prompt` — `KeyError` with
exit 1.

**Done:** `check_definition` runs once, on load, and refuses with exit 2 naming the block,
the missing field, the file and the example. Two more checks came with it, named here
because they are more than the finding asked for: `id` and `slug` become file names under
`docs/review/`, so a path separator in them is refused; and two blocks sharing an id are
refused, since the id is the block's name in the state, in the findings and in the reports.

**Commit:** `79aa8d6`
**Test:** `HandWrittenInputTest.test_блок_без_обязательного_поля_называет_поле` (forbidden,
across four commands: exit 2, no traceback, the field and the file named),
`test_полностью_заполненный_блок_принимается` (allowed),
`test_два_блока_с_одним_идентификатором_отказ`, `test_разделитель_пути_в_идентификаторе_отказ`
**Red on revert:** yes — `check_definition` call removed, build ok, all of them red.

---

## T1-011 · low · the freshness gate silently inert

**Re-checked:** reproduced — no remote and a remote named `upstream` both gave `check`
exit 0 with no mention of freshness.

**Done:** every remote is asked, `origin` first (`mainline_ref`). When git knows of no main
line at all, `check` says the gate is not running and names the command — `git remote add
origin … && git fetch`, or `git remote set-head <remote> -a`. A warning, not a failure: a
repository with no remote is legitimate, and a gate that refuses legitimate states is the
one people switch off.

**Commit:** `936e621`
**Test:** `FreshnessGateTest.test_удалённый_не_origin_ловит_отставание` (the case the
finding is about), `test_origin_по_прежнему_ловит_отставание` (allowed: the old path still
works), `test_без_удалённого_репозитория_ворота_объявляют_себя_неработающими` and
`test_удалённый_без_HEAD_называет_команду` (the inertness is spoken)
**Red on revert:** yes — only `origin` asked, build ok, test red; the notice removed →
its test red.

---

## T1-012 · medium · a cut-off run written to the journal as an ordinary one

**Re-checked:** reproduced with a stub `claude` that exits 1 — the journal line was written
unchanged.

**Done:** the journal line carries the run's outcome. `run-role.sh` puts the exit code into
it ("RUN FAILED (claude exit N — the assignment was NOT completed)"); what the stream itself
says about the ending comes from `axes.py` (see T1-017). The parenthetical half of the
finding is fixed too: a failing `review prompt` no longer leaves a zero-byte prompt file in
`TMPDIR`.

**Commit:** `3230faa`
**Test:** `SpendTest.test_упавший_прогон_записан_в_дневник_как_упавший` (forbidden),
`test_успешный_прогон_записан_обычной_строкой` (allowed — a successful run is still one
ordinary line, with no scary words in it),
`test_несобравшийся_промпт_не_оставляет_пустого_файла`
**Red on revert:** yes — the exit-code branch disabled → the first red (and the second
still green, which is the point); the prompt cleanup disabled → the third red.

---

## T1-013 · low · renames and quoted paths in the churn count

**Re-checked:** reproduced and re-measured on this repository: `review.py` has 42
first-parent commits with `--follow` and 10 under its current path; a Cyrillic path comes
out of `git log --name-only` C-quoted.

**Done:** `commit_file_sets` reads `--name-status -z -M` and translates every path into the
name it bears today, walking the log newest-first and applying each rename to everything
older. Measured after the fix: 42 commits for `review.py`, exactly matching `git log
--follow`, and no old name left in the sets.

**Commit:** `83a41c1`
**Test:** `GitTruthTest.test_переименование_не_обрывает_историю_изменений_блока` — the block
that owns the renamed file is credited with all six commits, not the one after the move.
**Red on revert:** yes — rename aliasing disabled, build ok, test red.

---

## T1-014 · low · the named-files gate is a substring test

**Re-checked:** reproduced — a report naming only `src/api.ts.snap` and `src/x.py` left
`missing = []`.

**Done:** a path must be named whole: what follows may not continue the name, what precedes
may not be the tail of a longer one. A trailing period is a sentence, not a longer path.

**Commit:** `242f88b`
**Test:** `ReportShapeTest.test_соседний_файл_с_тем_же_началом_не_закрывает_гейт_имён`
(forbidden) and `test_названный_файл_в_конце_предложения_засчитывается` (allowed — the
second one matters more: a gate that stops accepting honest reports is discovered by the
person whose work it refuses).
**Red on revert:** yes — the substring test restored, build ok, the first red.

---

## T1-015 · low · the mass-commit cutoff on a young history

**Re-checked:** reproduced over synthetic histories of 1…100 commits: for n ≤ 20 the cutoff
equalled the largest commit.

**Done:** the percentile is taken by nearest rank (the textbook definition, and the one that
leaves the top of the distribution outside the cutoff), and below a sample floor of 20 — the
size at which a 95th percentile can first separate anything — the outlier is found by
Tukey's fence, Q3 + 1.5·IQR. Measured after the fix: on `[1, 2, 2, 3, 120]` the cutoff is 4,
so the whole-tree commit is skipped and nothing else is; on a uniform history, where there is
no outlier, nothing is skipped. `coupling` prints which of the two rules produced the number.

**Commit:** `e6d52b2`
**Test:** `ThresholdTest.test_на_молодой_истории_стартовый_коммит_считается_массовым`
(forbidden: the initial commit is skipped and its pairs do not survive; the real cross-block
pair still does) and `test_на_длинной_истории_порог_остаётся_процентилем` (allowed: on a
history past the floor the percentile is still what speaks).
**Red on revert:** yes — the old index restored, build ok, test red.

---

## T1-016 · low · `summary --aged` cut at the first ` -->`

**Re-checked:** reproduced — a block titled `Import --> export pipeline` gave
`JSONDecodeError: Unterminated string`, exit 1.

**Done:** the machine block is one line; it is cut at the last `-->` of that line, and a
block that is not closed or not valid JSON gets a refusal naming the command that
regenerates it.

**Commit:** `79aa8d6`
**Test:** `HandWrittenInputTest.test_итог_с_маркером_внутри_названия_блока_не_роняет_aged`
(allowed) and `test_испорченный_машинный_блок_итога_объясняет_себя` (the refusal, with no
traceback)
**Red on revert:** yes — the old cut restored, build ok, both red.

---

## T1-017 · low · a stream without a result event reported as free

**Re-checked:** reproduced on three synthetic streams — complete, with the `result` event
removed, and with the last line cut short.

**Done:** without a `result` event there is no measurement, and the line says so: turns,
duration, output and cost print as `?`, never as zero, and the outcome leads the line. A
`result` whose subtype is not `success` — what the client writes when the turn cap trips —
is reported as `RUN CUT OFF` with the subtype. An unreadable last line is counted and named
instead of raising, because dying there costs the journal line, the agent's reply and the
run's exit code.

**Commit:** `3230faa`
**Test:** `SpendTest.test_поток_без_события_result_не_выдаётся_за_измерение`,
`test_обрезанная_последняя_строка_не_роняет_замер`,
`test_прогон_обрезанный_потолком_ходов_назван_обрезанным` (forbidden) and
`test_целый_поток_по_прежнему_читается_как_замер` (allowed: a complete stream still prints
the real numbers, and no scary words)
**Red on revert:** yes, all three mutations, builds ok.

**Coverage limit, carried over from the verifier and still open:** `claude -p` was never run
for real. The stub reproduces the shapes (a non-zero exit, a stream with no `result` event,
a truncated final line, a `result` with a non-success subtype), and the fix keys on
`subtype != "success"` rather than on one exact string, so it does not depend on the cap's
subtype being spelled `error_max_turns`. What the real client writes at the cap is still
unobserved here.

---

## T1-018 · low · `init` dirties state.json on a no-op re-run

**Re-checked:** reproduced — two consecutive runs differed only in `updated_at`.

**Done:** `init` writes only when the state would actually change; the stamp says when the
state last changed, so it is the one field excluded from the comparison. The same was done
for `restamp`, of a block and of a finding — the invariant names both.

**Commit:** `79aa8d6`
**Test:** `IdempotenceTest.test_повторный_init_не_меняет_состояние_ни_на_байт` (forbidden)
and `test_init_на_изменившемся_определении_состояние_меняет` (allowed — a real change is
still written, which is what the early return could have broken)
**Red on revert:** yes — the early return disabled, build ok, test red.

---

## T1-019 · medium · the coverage gate satisfied by "I completed the check"

**Re-checked:** reproduced — a verifier report whose whole body was "I completed the check
of every finding; nothing was confirmed." passed `verify_report_problem`.

**Done:** `complete` must be a word, not the head of `completed` — a verb about the work
done, not a statement about coverage. The Russian side takes every form of `полн-`
(полный, полностью, полнота) for the same reason the English side takes `completely`: the
adjective and the adverb are the same statement, and matching only the adjective refused
an honest report.

**Commit:** `242f88b`
**Test:** `ReportShapeTest.test_завершил_проверку_не_оценка_охвата` (forbidden) and
`test_честная_оценка_охвата_принимается_на_обоих_языках` (allowed, both languages)
**Red on revert:** yes — the old regex restored, build ok, both red.

**One half of the finding is not implemented, deliberately.** The verifier also reported
that "все находки проверены" ("all findings are checked") matches nothing and so an honest
Russian report is refused. That sentence is the Russian of "I completed the check of every
finding" — the very sentence the other half of this finding requires the gate to reject. A
verdict about findings is not a verdict about coverage; the gate's whole job is to keep the
two apart, and the neighbouring hunter gate is strict about exactly that distinction.
Making it match would reopen the false pass this finding exists to close. Recorded, not
silently dropped.

---

## T1-020 · low · four thresholds with no source

**Re-checked:** read against every other constant in the file; the four carry none.

**Done:** each now carries its measurement, taken here and reproducible:

- `REF_LIST_LIMIT = 80` — a path in this tree is 31 characters on average (90th percentile
  45), so 80 of them are ~2 500 characters, about 600 tokens;
- the manifest emptiness bound, now `MANIFEST_MIN_CHARS = 200` — the six headings of
  `assets/manifest.example.md` come to 171 characters, and a manifest copied and not filled
  in is exactly that file with the text deleted; the shortest real manifest measured here is
  4 743 characters;
- `CLAIM_MAX = 220` / `SCENARIO_MAX = 700` — over the 24 findings of this block the claim
  runs 82…202 characters (median 178, 90th percentile 194) and the scenario 452…690 (median
  586, 90th percentile 665); both caps sit just above the longest real one;
- the coupling hub threshold is no longer a bare 6: `hub_blocks()` is a share of the review's
  blocks (10%) with a floor of three — two blocks are a seam, a third makes it a node — and
  the share reproduces the 6 the kit ran with on the 59-block review it came from
  (59 × 10% = 5.9 → 6), where a fixed 6 was unreachable on a small review.

**Commit:** `e6d52b2`
**Test:** `SourceRuleTest.test_каждое_число_в_коде_названо_и_объяснено` — the guard, not a
list: every module-level numeric constant must carry a comment above it (a comment above a
group counts for the group).
**Red on revert:** yes — a bare `NEW_LIMIT = 42` added, build ok, test red.

---

## T1-021 · low · substitution into what was already substituted

**Re-checked:** the half fixed before the fix phase (the placeholder check on the template)
holds; the quieter mirror reproduced — a manifest sentence about `{{FILES}}` rendered as the
file list.

**Done:** one pass over the template. What the template asks for is substituted; what the
substituted text contains is quotation.

**Commit:** `79aa8d6`
**Test:** `HandWrittenInputTest.test_подстановка_в_тексте_манифеста_остаётся_текстом`
(forbidden) and `test_подстановки_самого_шаблона_по_прежнему_заполняются` (allowed — the
template's own placeholders are still filled, which a careless one-pass fix could break)
**Red on revert:** yes — the loop restored, build ok, test red.

---

## T1-022 · medium · one marker exempts every hit in the window

**Re-checked:** reproduced — a file with one marker and four forbidden calls reported one.

**Done:** the search runs upwards from the nearest line, and the marker that covers a hit is
spent: the next hit below it needs its own. That is what the script's header promised and
what `grep -B` could not do.

**Commit:** `e479137`
**Test:** `GuardGrepTest.test_один_маркер_освобождает_один_вызов` (forbidden: three of four
calls are reported now, the one under the marker is not) and
`test_каждому_вызову_свой_маркер_и_дерево_чистое` (allowed: a marker per call, including a
trailing comment on the line itself, still leaves the tree clean and exit 0)
**Red on revert:** yes — the spend removed, both tests red.

---

## T1-023 · low · a pathspec git refuses to parse

**Re-checked:** reproduced — `check` and `coverage` exited 1 with `CalledProcessError`.

**Done:** `index_rows` reads git's exit code and refuses with git's own message, the
patterns it was given and the file they live in.

**Commit:** `83a41c1`
**Test:** `GitTruthTest.test_шаблон_который_git_отказывается_разобрать_объясняет_себя`
(forbidden: exit 2, no traceback, `blocks.json` named) and
`test_законный_шаблон_с_исключением_по_прежнему_работает` (allowed: `:(exclude)…`, the magic
the kit invites projects to use, still works)
**Red on revert:** yes — `check=True` restored, build ok, the first red.

---

## T1-024 · low · a string line number skips the cited-line gate

**Re-checked:** reproduced — `check` reported only the integer one; `findings.md` rendered
both.

**Done:** the type is part of the vocabulary, next to `severity`, `confidence` and `status`:
a `line` that is not a whole number is a problem naming the fix, and the range check runs
on the numbers.

**Commit:** `242f88b`
**Test:** `GateCoverageTest.test_номер_строки_строкой_а_не_числом` (forbidden) and
`test_число_в_пределах_файла_по_прежнему_проходит` (allowed)
**Red on revert:** yes — measured as gate 33 of the 62-gate run: silenced, build ok, test red.

---

# Guards: which class is closed by which rule

Three roots reached `ROOT_RULE_AT` (three instances) and one more reached it counting a
third address found while fixing. Each guard was run against the defect it exists to stop.

| root | instances | guard | red on the defect |
|---|---|---|---|
| report parser matches shape, not meaning | 7 (T1-001…004, 014, 019, 024) | `tests/test_review.py::ReportShapeTest` — 13 paired cases: fences, code spans, tables, path prefixes, coverage wording, in both languages and both directions; plus `SourceRuleTest.test_ограды_кода_распознаются_одним_местом`, which forbids a second fence detector anywhere in the tool | yes — a second fence detector added → red; each parser revert → red |
| a gate that cannot go red | 4 (T1-007, 008, 011, 022) | `tests/test_review.py::GateRegistryTest` — the gate → test table in code, inventory taken from the source with `ast` | yes — an unregistered `problems.append` added → red; an entry naming a nonexistent test → red |
| hand-edited input reaches the code unvalidated | 4 (T1-010, 016, 021, 023) | `tests/test_review.py::HandWrittenInputTest` — including the rule that takes the subcommand list from the tool itself, so no command can reach a malformed definition with a traceback, and a new command falls under the rule without the test being edited | yes — `check_definition` removed → red |
| git output parsed as plain text, without `-z` | 2 recorded (T1-006, T1-013) + a third address found while fixing (`summary --aged`) | `tests/test_review.py::SourceRuleTest` — a git command that asks for file names must pass `-z`, checked over the source with `ast` | yes — `-z` dropped from one `ls-files` call → red |
| threshold without its source | 1 (T1-020) | `tests/test_review.py::SourceRuleTest` — every module-level numeric constant carries its source above it | yes — a bare constant added → red |

# Incidental fixes, each named with its own test

Found while fixing, in the same class as a finding but not named by one.

1. **`block_lines` counted a binary file as lines and read the disk** — the same question
   `file_lines` answers, asked a second time and answered worse: a picture inflated a block
   against the readability ceiling. Now counted through `file_lines`.
   Commit `83a41c1`; test `GitTruthTest.test_двоичный_файл_не_считается_строками_в_пороге`;
   red on revert (the private `open()` loop restored), build ok.
2. **`summary --aged` parsed `git log --name-only` by lines** — the third address of the
   class T1-006 and T1-013 belong to, found by `grep` rather than from the findings' list.
   Now `-z` with an `\x01` commit marker. Commit `83a41c1`; held by the guard
   `SourceRuleTest.test_список_путей_у_git_всегда_запрашивается_NUL_разделённым`, which goes
   red when `-z` is dropped from any such call; the command itself is exercised by
   `HandWrittenInputTest.test_итог_с_маркером_внутри_названия_блока_не_роняет_aged`.
3. **`restamp` was not idempotent**, for a block and for a finding — the invariant names
   both alongside `init`. Commit `79aa8d6`; tests
   `IdempotenceTest.test_повторный_restamp_блока_ничего_не_пишет`,
   `test_повторный_restamp_находки_ничего_не_пишет`, and
   `test_restamp_после_правки_файлов_отпечаток_переснимает` for the other direction; red on
   revert, build ok.
4. **A block definition with a path separator in `id`/`slug`, and two blocks sharing an
   id** — more than T1-010 asked for: `id` and `slug` become file names under
   `docs/review/`. Commit `79aa8d6`; tests
   `HandWrittenInputTest.test_разделитель_пути_в_идентификаторе_отказ`,
   `test_два_блока_с_одним_идентификатором_отказ`; red on revert, build ok.
5. **A draft findings file carrying one id twice** was accepted by `import` — the other
   half of the id-uniqueness question T1-009 opens. Commit `79aa8d6`; test
   `IdempotenceTest.test_две_строки_с_одним_номером_в_черновике_отказ`; red on revert,
   build ok.
6. **`run-role.sh` left a zero-byte prompt file** after a failing `review prompt` — named
   inside T1-012's scenario, fixed with it. Commit `3230faa`; test
   `SpendTest.test_несобравшийся_промпт_не_оставляет_пустого_файла`; red on revert.
7. **`listed()`'s docstring** said "without submodules and symlinks" while the comment above
   it explains at length why a symlink IS a file here. Corrected with the function; no test —
   it is a sentence, not a mechanism.

# What the fix phase deliberately did not touch

- **The hunter report's own contradictory verdicts.** `check` reports six hypotheses to
  which `T1-tool.hunter.md` gives two verdicts (T1.2, T1.3, T1.5, T1.7, T1.11, T1.12).
  Measured against the parser as it was before this work and as it is now: the same six,
  neither created nor removed by the parser fix. They are contradictions in the text of a
  report — an artifact of the review, not of the code — and a fixer editing a hunter's
  report to turn a gate green is the shape of defect this whole block is about. Left for
  acceptance.
- **The block fingerprint.** `check` says the block's files changed after the review,
  which is exactly what a fix phase does. `restamp T1` is the diff reviewer's call, not
  the fixer's.

# Rejected findings

None. All 24 were reproduced on the current code before being touched.

Two findings are closed with a named half left undone, for reasons that are stated in full
in their sections above and are not omissions: **T1-003** (a bare "verified" in prose cannot
be told from a legitimate verdict by any mechanical rule without refusing honest reports)
and **T1-019** (matching "все находки проверены" would reopen the false pass the other half
of the same finding closes).

# Gates

```
$ python3 -m unittest discover -s tests
.........................................................................................
.........................................................................................
...........................
----------------------------------------------------------------------
Ran 205 tests in 151.537s

OK

$ npx skills-ref validate skills/finetooth
Valid skill: skills/finetooth
```

118 tests before this work, 205 after: 87 new, of which 28 close T1-007 and the rest come
in pairs — what is now forbidden, and what must still pass.

## Mutation run 1 — every gate of `check`, one mutant per gate

Each gate silenced in its own copy of the kit (the statement replaced by `pass`), the copy
compiled, and the registered test run against it.

```
gates registered: 62
  1 build ok | red | ': no record in state.json — run ` init`' -> GateCoverageTest.test_блок_из_определения_без_записи_в_состоянии
  2 build ok | red | ': present in state.json but missing from blo' -> GateCoverageTest.test_блок_в_состоянии_которого_нет_в_определении
  3 build ok | red | ": status '' is not in the vocabulary — writt" -> ReviewToolTest.test_статус_блока_вписанный_руками_роняет_проверку
  …
 62 build ok | red | 'open finding(s) older than days (oldest d): ' -> ReviewToolTest.test_check_предупреждает_о_находке_старше_недели

=== gates whose test did not detect the removal: 0
```

## Mutation run 2 — every fix reverted

```
build ok | red | T1-001 fences are not skipped in verdict_mentions
build ok | red | T1-002 a bare numbered first row is a header again
build ok | red | T1-003 code spans are not unquoted
build ok | red | T1-004 ~~~ is not a fence
build ok | red | T1-019 the old coverage regex
build ok | red | T1-005 file_sha gives up when the file is not on disk
build ok | red | T1-005b block_lines counts by itself again
build ok | red | T1-006 the fix gate reads quoted paths again
build ok | red | T1-013 renames stop being followed
build ok | red | T1-023 git's refusal raises again
build ok | red | T1-014 the named-files gate is a substring test again
build ok | red | T1-011 only origin is asked
build ok | red | T1-009 ids by position again
build ok | red | T1-009b a duplicate id in the draft is accepted
build ok | red | T1-010 the definition is not validated
build ok | red | T1-016 the machine block is cut at the first ' -->'
build ok | red | T1-018 init always rewrites the stamp
build ok | red | T1-018b restamp always rewrites the stamp
build ok | red | T1-018c restamp of a finding always rewrites
build ok | red | T1-021 substitution in several passes again
build ok | red | T1-015 the old percentile index
build ok | red | T1-017 a stream without a result event is a measurement again
build ok | red | T1-017b a truncated last line raises again
build ok | red | T1-017c the turn cap leaves no trace
build ok | red | T1-012 the journal does not carry the exit code
build ok | red | T1-012b a failed prompt leaves its file behind
build ok | red | T1-008 a missing scan path is skipped again
build ok | red | T1-022 a marker is not spent
build ok | red | guard: a git path list without -z
build ok | red | guard: a second fence detector
build ok | red | guard: a number without a source
build ok | red | guard: a new gate without a test
build ok | red | guard: a registered test that does not exist

=== mutants that did not turn their tests red: 0
```

## The suite at every commit of the series

A history whose middle commit is red cannot be bisected. Each commit was checked out into
its own worktree and the whole suite run against it.

```
242f88b OK  Report parsing: a verdict is content, not shape              | Ran 131 tests in 101.3s  OK
83a41c1 OK  git is the source of file truth, and paths travel NUL-separa | Ran 138 tests in 103.4s  OK
79aa8d6 OK  What a human edits by hand gets a refusal, not a traceback   | Ran 155 tests in 120.5s  OK
936e621 OK  The freshness gate says when it cannot run                   | Ran 159 tests in 129.7s  OK
e6d52b2 OK  Thresholds that hold at the edge of their range              | Ran 161 tests in 128.8s  OK
3230faa OK  A cut-off run is recorded as cut off                         | Ran 168 tests in 134.3s  OK
e479137 OK  guard-grep: one marker frees one call, a missing path refuses| Ran 171 tests in 133.2s  OK
7b55f5c OK  Every gate of `check` under a test, and three guards         | Ran 204 tests in 149.5s  OK
2ce050d OK  0.8.0: the review of the tool itself, in the changelog       | Ran 204 tests in 151.5s  OK
```

The tenth commit (`f90c68d`) landed after that run started and is covered by the full-tree
run quoted above.

## What `check` still says about the block, and why it is not the fixer's to close

```
WARNINGS (do not fail the check):
  · T1: context files (ref_paths) changed after verification …

CHECK FAILED:
  · T1: T1-tool.hunter.md gives hypothesis T1.2 different verdicts (checked / not checked) …
  · T1: T1-tool.hunter.md gives hypothesis T1.3 different verdicts …
  · T1: T1-tool.hunter.md gives hypothesis T1.5 different verdicts …
  · T1: T1-tool.hunter.md gives hypothesis T1.7 different verdicts …
  · T1: T1-tool.hunter.md gives hypothesis T1.11 different verdicts …
  · T1: T1-tool.hunter.md gives hypothesis T1.12 different verdicts …
  · T1: block files changed after the review — … `restamp T1`
```

Both are addressed in "What the fix phase deliberately did not touch" above: the six are
contradictions in the hunter's own text, identical before and after the parser fix, and the
fingerprint is the diff reviewer's to re-take.
