# T1 — fix phase, round 2 (the findings of fix review round 1)

Seven findings, one medium and six low. **Closed 7, rejected 0.** Every one was reproduced
in the current code before it was touched, every fix carries a test, and every test was
checked by reverting the fix with the build intact.

## Gates run

```
$ python3 -m unittest discover -s tests
.......................................................................................
...............................................................................
----------------------------------------------------------------------
Ran 217 tests in 204.027s

OK

$ npx skills-ref validate skills/finetooth
Valid skill: skills/finetooth
```

205 tests before this round, 217 after: twelve added and none removed — the two
registry-shape tests, the commit-record guard, the drift count, the two named-files
directions, the two quotation directions, the three `axes` result tests and the
fix-template rule test. One test was renamed with the rule it holds
(`test_ограды_кода_распознаются_одним_местом` → `test_цитаты_распознаются_одним_местом`).

## The findings

### T1-025 · medium · the gate registry does not see a gate whose message is not a literal

**Reproduced first.** Added to `cmd_check` a gate with no test at all:

```
$ # if st.get("review_id") != defn.get("review_id"): msg = f"..."; problems.append(msg)
$ python3 -m unittest tests.test_review.GateRegistryTest
Ran 2 tests in 0.105s

OK          <- the defect: a gate with no test, and the registry is content
```

**What was done** → `6ae9c90`. A gate whose message carries no wording of its own (the whole
text comes from a helper or a variable) is keyed by the expression that produces it, not by
an empty literal skeleton; and the registry compares **counts**, not sets, so two gates can
never collapse into one entry whatever the key. The two entries whose key changed
(`verify_report_problem`, `dup_problem`) were rewritten in `GATES`.

**Which test catches it** — `GateRegistryTest.test_ворота_с_сообщением_из_переменной_не_теряются`
(the forbidden direction: two gates of the two non-literal shapes must not share a key and
must not match anything registered) and
`test_ворота_с_литеральным_сообщением_читаются_как_раньше` (the allowed direction: an
ordinary f-string is still recognised by its wording, so editing a substituted value does
not fail the registry).

**Red on the reverted fix** — yes, build ok:

```
$ # _check_gates back to the literal-only key, the comparison back to sets
$ python3 -c "import ast,pathlib; ast.parse(...)"   → build=ok
AssertionError: 1 != 2 : ворота слились в один ключ: ['', '']
Ran 4 tests ... FAILED (failures=1)
```

And the real mutation, both shapes, against the fixed registry — build ok, red in both:

```
problems.append(msg)                → ['= msg']                    ворота без записи в GATES
problems.append(dup_problem(f, {})) → ['= dup_problem(f, {})']     ворота без записи в GATES
```

### T1-026 · low · `summary --aged` counted one file under two names

**Reproduced first**, on the raw stream: `git log --format=%x01%H --name-only -z` emits
`\x01<sha>\0` + `\nsrc/a.ts\0src/b.ts\0` — the newline that ends the `--format` line is
glued to the first path of every commit. Two commits over two files printed `files: 3`.

**What was done** → `f0d37eb`. The defect has two addresses, and only one of them knew about
the trap: `commit_file_sets` stripped the newline, the drift query of `cmd_summary`, written
later, did not. Both now go through one reader, `log_records`, which returns
`(sha, [tokens])` per commit. `commit_file_sets` was rewritten onto it without a change of
behaviour — measured: `order` still credits `review.py` with 50 commits, the number
`git log --follow --first-parent` gives through both of its renames.

**Which test catches it** — `test_дрейф_не_считает_один_файл_дважды` (two commits, the second
touching only the file that was second in the first commit → `files: 2`).

**Red on the reverted fix** — yes, build ok:

```
AssertionError: Regex didn't match: 'H1\s+\S+: 2\s+\S+: 2' not found in
  'H1     коммитов: 2     файлов: 3     Демоблок'
```

**The class guard** — `SourceRuleTest.test_записи_коммитов_разбираются_одним_местом`: reading
the commit marker back anywhere but inside `log_records` fails the suite. Red on the defect:
with the old inline parse restored it reports
`[('cmd_summary', 1402), ('cmd_summary', 1403)]`.

### T1-027 · low · the named-files gate refused `./src/api.ts`

**Reproduced first**, on the parser: with `rel = src/api.ts`, `names_file` answered `False`
for `- ./src/api.ts`, `--- a/src/api.ts` and `+++ b/src/api.ts`.

**What was done** → `b99eda3`. The lookbehind that stops `docs/src/api.ts` closing the gate
for `src/api.ts` now allows exactly three prefixes in front of the path — `./`, `a/`, `b/` —
and only where the prefix itself starts a path.

**Which tests catch it** — both directions:
`test_путь_с_приставкой_точки_или_заголовка_диффа_засчитывается` (a report writing `./src/api.ts`
and `--- a/src/util.ts` passes `check` with rc 0) and
`test_приставка_не_делает_названным_файл_из_другого_каталога` (`docs/src/api.ts` and
`lib/a/src/api.ts` still do not name `src/api.ts`).

**Red on the reverted fix** — yes, build ok: the first test fails with
`'not named by full' unexpectedly found` while the second stays green (it guards the
direction the old code already had). And the opposite mutation — the prefix widened to any
directory — turns the second test red, so the new allowance cannot be loosened silently.

### T1-028 · low · a verdict quoted by an indent, by `>` or in a comment still closed a hypothesis

**Reproduced first**, on `verdict_mentions` with block id `T1`:

```
fence     {}                        <- closed in the previous round
indent    {'T1.1': ['checked']}     <- four-space indented example
quote     {'T1.1': ['checked']}     <- `> - T1.1 — checked: …`
comment   {'T1.1': ['checked']}     <- `<!-- - T1.1 — checked: … -->`
```

**What was done** → `7a53ce3`. Recognising a quotation now lives in one function,
`quoted_lines`, which knows all four of markdown's forms, and every markdown parser of the
tool (`demote`, `section_body`, `section_items_full`, `verdict_mentions`) calls it — the
previous round had already made the fence one tracker for exactly this reason, and a fix in
the verdict parser alone would have split them again.

The hard half is the indented block, because the same indentation is how a report writes its
proof under a verdict. The implementation follows CommonMark: an indented code block cannot
interrupt a paragraph (a blank line must come first) and its column is measured from the
enclosing list item's content column, so a sub-item under a hypothesis stays part of it.
Checked on a matrix of 21 report shapes, 12 of which must keep their verdict — all 21 agree
with what the reader of the report would see. The three real reports of this block and the
manifest parse **identically** before and after (`verdict_mentions` equal on all four files,
15 hypotheses before and after), so the change moves no verdict of the review under way.

The renaming caught a live collision on the way: the new list-marker pattern was first
called `LIST_MARK`, a name already taken further down the file, and the later definition won
at call time. The class guard found it before any test did.

**Which tests catch it** — both directions:
`test_вердикт_внутри_отступа_или_цитаты_не_вердикт` (three subtests, one per form → `closed 0/1`)
and `test_вердикт_под_своей_гипотезой_с_отступом_по_прежнему_вердикт` (a verdict written as a
four-space sub-item under a list item → `closed 1/1`).

**Red on the reverted fix** — yes, build ok: with `verdict_mentions` back on the fence-only
tracker, all three subtests fail (`'NO VERDICT' not found`) and the second test stays green.

**The class guard** — `SourceRuleTest.test_цитаты_распознаются_одним_местом`, rewritten from a
`count(...) >= 4` threshold (which the previous round's review correctly called weaker than
it reads) into two AST rules: the detection constants may be referenced only inside the two
tracker functions, and each of the four markdown parsers must call `quoted_lines`. Red on the
defect: the same revert reports `разборщик markdown не зовёт общий трекер цитаты`.

**A change to a mechanism is a change to a prompt** — `hunter.md`, `hunter.ru.md`,
`verify.md`, `verify.ru.md` now name all four forms, and
`test_шаблоны_ролей_говорят_где_писать_вердикт` checks each form in each of the four files
(on whitespace-normalised text, because the templates are wrapped to width).

### T1-029 · low · `axes.py` changed which `result` event it measures, unrecorded and untested

**Reproduced first**, on synthetic streams — a 40-turn `success` and a 2-turn
`error_max_turns`, in both orders:

```
two-results-ok-first    spend: 10 min, 40 turns … $5.00      <- no outcome word
two-results-cut-first   spend: 10 min, 40 turns … $5.00      <- no outcome word
more-msgs-than-turns    spend: ? min, 2 turns, 11 tool calls … $67.92
```

**What was done** → `f7da53c`. The heuristic itself is right and is now written down where it
is applied: the **numbers** come from the longest result event, because a turn cap trips on
the longest branch by construction. The **outcome** is a different question and is now read
from every result event — the cut-off is recorded in the short one, and that is the safety
switch's only trace in the journal.

The second half of the finding — a journal line that reads as a measurement and cannot be
one — was closed too, and by a measurable rule rather than a caveat: a turn carries at most
one assistant message, so a stream holding more assistant messages than the result claims
turns is a result about part of the run. The line then says `PARTIAL RESULT — 11 assistant
messages in the stream against 2 turns in the result` instead of printing a spend.

**Which tests catch it** — `test_обрезка_во_втором_событии_result_не_теряется` (both orders,
and the numbers still from the long event), `test_результат_короче_потока_не_выдаётся_за_замер_прогона`,
and the allowed direction `test_два_успешных_события_result_не_объявляются_обрезкой` (two
finished events are an ordinary run — no cut-off word, no partial-result word).

**Red on the reverted fix** — yes, build ok: outcome back to one event → the first test fails
with `'RUN CUT OFF' not found`; the consistency check silenced → the second fails with
`'PARTIAL RESULT' not found`; the third stays green on the old code.

**Recorded** — the change now has its entry in `CHANGELOG.md` and `CHANGELOG.ru.md`, which was
half of what the finding asked for.

### T1-030 · low · the Breaking section held five fixes that are not breaking, and not the change that is

**Reproduced first.** A `blocks.json` with `"phase": "1"` — legal before this round — against
the current tool:

```
status: rc=2  error: docs/review/blocks.json: block H1 has no whole-number `phase` …
check:  rc=2  (same)
order:  rc=2  (same)
```

**What was done** → `341c56d`. The `[Unreleased]` section now has one heading per type in both
languages, Breaking last, as the released sections below it are written. The five bullets
that a heading inserted mid-list had swept out of `Fixed` are back in `Fixed`; the two
`Added` and the two `Breaking` sections are merged; and the change a running review has to
act on — the validation of block definitions — is written up in Breaking with what to do
about it (fix the field the message names; nothing on disk has to be regenerated).

Two more Breaking entries were owed and are there: this round's quotation forms (a running
review whose reports quoted their verdicts will show them unanswered) and the note that a
sub-item indented under a verdict still belongs to it.

**Which test catches it** — none, and none is claimed: this is prose about prose. What a test
does hold is the half of the finding that is a rule — see T1-031. The state check holds the
rest: `check` refuses a finding record whose scenario exceeds the limit, which is how the
over-long record of this very finding was caught (see "New findings").

### T1-031 · low · two new rules in the fix role template, recorded nowhere

**Reproduced first**: `grep` for the rules across `CHANGELOG*`, `tests/` and `docs/review/`
found them only in `references/fix.md` and `references/fix.ru.md` themselves.

**What was done** → `341c56d`. A changelog entry in both languages, and a test that keeps the
rules in both templates — the way the sibling rule about where a verdict is written is kept.

**Which test catches it** —
`test_шаблон_исполнителя_держит_правила_выпуска_и_расхода`: four phrases per template, two
per rule, in both languages, on whitespace-normalised text.

**Red on the reverted fix** — yes, build ok (a template is data, and the file still parses):
with rules 11 and 12 cut out of `fix.md`, the test fails on all four English phrases.

## Incidental fixes

1. **`commit_file_sets` rewritten onto `log_records`** (`f0d37eb`). Not a defect of its own —
   it already stripped the glued newline — but leaving two readers of the same stream is the
   condition that produced T1-026. Behaviour checked to be unchanged by measurement on this
   repository's own history (`order`: `review.py` still 50 commits, chained renames included)
   and by the existing `GitTruthTest`/`ThresholdTest` suites.
2. **`LIST_MARK` collision** (`7a53ce3`). The new list-marker pattern shadowed an existing
   module-level constant of the same name, and the later definition won at call time, so
   `quoted_lines` was silently using the wrong regex. Renamed to `LIST_OPEN`. Caught by the
   new class guard (`test_цитаты_распознаются_одним_местом`), which is also the test that
   holds it: the guard names the detection constants, so a second shadowing would fail it.
3. **The fence class guard replaced by a rule** (`7a53ce3`). The previous round's guard
   asserted `SOURCE.count("fenced_lines(") >= 4` against five occurrences — removing a caller
   kept it green, as that round's own review noted. It is now two AST rules with no
   threshold: detection constants only inside the trackers, and every named markdown parser
   must call `quoted_lines`. Red on the defect, shown under T1-028.
4. **The over-long scenario of finding T1-030 trimmed** in `findings.jsonl` (624 characters
   against the limit of 700), and `findings.md` regenerated. Register bookkeeping, not code:
   the record was written over the limit because nothing at import time stops it — which is
   a finding of its own, below.

## New findings (reported, not fixed)

- **`import` accepts a finding that `check` will refuse.** `CLAIM_MAX` and `SCENARIO_MAX` are
  enforced only in `cmd_check`; `import` writes the row and says nothing, so the register
  goes red on the next `check` with no way to tell which agent wrote it or when. Measured:
  the record of T1-030 was imported with a 793-character scenario and failed `check`
  immediately (`finding T1-030: scenario is 793 characters against a limit of 700`). A
  different kind of defect from the seven above, so it is named here rather than fixed
  inside someone else's finding — the rule is `check` demanding what nothing else produces.

## Rejected findings

None. All seven were reproduced in the current code before being touched.

## Left for acceptance

- **`restamp T1`** — the block fingerprint is stale because the fix phase changed the block's
  files, which is what a fix phase does. As in round 1, this is the diff reviewer's call.
- **The hunter report's six contradictory verdicts** (T1.2, T1.3, T1.5, T1.7, T1.11, T1.12).
  Measured again here: `verdict_mentions` gives byte-identical results on all four reports of
  the block before and after this round's parser change, so the contradictions are the
  report's own and are not touched — a report is not code, and the fixer does not rewrite it.
