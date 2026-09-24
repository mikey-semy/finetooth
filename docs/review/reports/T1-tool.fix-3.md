# T1 — fix phase, round 3 (the findings of fix review round 2)

Five findings, two medium and three low. **Closed 5, rejected 0.** Every one was reproduced
in the current code before it was touched, every fix carries a test in both directions, and
every test was checked by reverting the fix with the build intact.

## Gates run

```
$ python3 -m unittest discover -s tests
.............................................................................................
.............................................................................................
............................................
----------------------------------------------------------------------
Ran 230 tests in 194.955s

OK

$ npx skills-ref validate skills/finetooth
Valid skill: skills/finetooth
```

217 tests before this round, 230 after: thirteen added and none removed — the two
fence directions, the three quotation-substance directions, the template rule, the two
diff-prefix directions, the three run-role directions, the guard's own two-sided rule and
the acceptance-criterion cell.

## The findings

### T1-032 · medium · a verdict inside a fence nested in a list item still closes a hypothesis

**Reproduced first.** `verdict_mentions` over a hypotheses section whose fence sits inside a
list item:

```
$ # - The task asked to write the verdict like this:
$ #
$ #     ```markdown
$ #     - H1.1 - checked: <proof>
$ #     - H1.2 - checked: <proof>
$ #     ```
indent4 {'H1.1': ['checked'], 'H1.2': ['checked']}      <- nothing was answered
    0 '    ```markdown'                                 <- the fence is not a fence
```

The cause is not the list: `FENCE` measured the indent from the MARGIN (`^\s{0,3}`), and a
fence inside a list item starts at the item's content column, four spaces in and beyond. A
`~~~` fence under a numbered item (indent 5) behaved the same way.

**What was done** → `74c7522`. Where a fence may open depends on the list item it sits in, so
a separate pass cannot decide it: `fenced_lines` is gone into `quoted_lines`, which now
tracks the fence in the same pass as the list context and lets it open (and close) up to
`FENCE_SLACK` = 3 spaces past the content column — the CommonMark 4.5 bound, next to the
`CODE_INDENT` = 4 it is derived from.

**Which test catches it** — `ReportShapeTest.test_ограда_внутри_пункта_списка_остаётся_оградой`
(the forbidden direction: a quoted skeleton in a list item closes nothing, `closed 0/2`) and
`test_вердикт_после_вложенной_ограды_по_прежнему_вердикт` (the allowed direction: the nested
fence closes on its own line and the verdict written below it is still read, `closed 1/1`).

**Red on the reverted fix** — yes, build ok (`ast.parse` on the reverted file: BUILDS):

```
AssertionError: 'NO VERDICT' not found in '  H1.1     checked … H1.2     checked … closed 2/2'
AssertionError: Regex didn't match: 'H1\.1\s+not checked' not found in '  H1.1     checked'
Ran 2 tests — FAILED (failures=2)
```

### T1-033 · medium · the gates that read a report's substance still count quoted text

**Reproduced first**, both halves:

```
verify_report_problem: None            <- a body that is one ```markdown fence and nothing else
limits body said: ['```markdown', '- src/legacy.ts - not read, generated', '```']
```

**What was done** → `94a0b48`. `unquoted(lines)` next to `quoted_lines` — the lines a text
SAYS — and both gates weigh the substance through it: `verify_report_problem` and the
coverage-limits gate of `cmd_check`. The three refusals now name where the answer belongs
("as an ordinary line and not inside a fence or a quotation"); the first 46 characters of the
two `cmd_check` messages are unchanged, so the gate registry keeps its keys.

A mechanism change is a prompt change: `hunter.md`, `hunter.ru.md`, `verify.md` and
`verify.ru.md` now say the rule covers **everything the state check reads in the report** —
the coverage-limits section, the verdict on each finding, the coverage statement — not the
hypothesis verdicts alone.

**Which test catches it** — `ReviewToolTest.test_отчёт_проверяющего_из_одних_цитат_не_проводит_блок`
and `test_раздел_ограничений_из_одной_цитаты_роняет_проверку` (forbidden, both halves);
`test_отчёт_проверяющего_с_образцом_рядом_со_словами_проходит` and the second case of the
limits test (allowed: an example beside real words changes nothing, `check` exit 0);
`ParallelKitLessonsTest.test_шаблоны_ролей_говорят_что_цитата_не_считается_нигде` (the prompt
rule, both languages, both roles).

**Red on the reverted fix** — yes, build ok (`unquoted` left defined, only the two call sites
reverted; `ast.parse`: BUILDS):

```
AssertionError: 0 != 1 : … review state is consistent          <- the verifier gate
AssertionError: False != True : … review state is consistent   <- the limits gate
Ran 3 tests — FAILED (failures=2)     <- the allowed direction stayed green, as it must
```

### T1-034 · low · the quotation guard cannot see a parser that does not exist yet

**Reproduced first**, and wider than the finding. Three shapes appended to `review.py`, the
guard run over the patched source each time:

| shape added to `review.py` | old guard |
|---|---|
| `report_sections(md)` pairing lines with `fenced_lines` (the finding's own example) | 4 tests, **OK** |
| `report_sections(md)` reading `#` and `\|` with no helper at all | 4 tests, **OK** |
| `limits_said(md)` reading the raw lines of `section_body` | 4 tests, **OK** |

**What was done** → `4ef5d7f`. The rule no longer holds a list of names. A markdown parser is
recognised by its shape — a document parameter (`md`, the tool's name for a markdown
document), a structural pattern of the markup (`FENCE`, `BLOCKQUOTE`, `LIST_OPEN`,
`LIST_ITEM`, `LIST_MARK`, any `*_HEADING`), a section's lines, or a per-line flag zipped with
them — and must ask `quoted_lines` or `unquoted`, itself or through what it calls. One
exception in the delegation: `section_body` hands its section's lines back **as they stand**
(it recognises a quotation to find the boundaries, not to drop it), so reading them obliges
the caller to ask the tracker. That exception is exactly the hole T1-033 fell through.

**Which test catches it** — `SourceRuleTest.test_цитаты_распознаются_одним_местом` (the rule
over the real source) and `test_узда_видит_разборщика_которого_ещё_нет`, which runs the same
rule over five synthetic sources: three parsers that must be seen, and two that must not —
a JSONL reader whose `#` opens a comment (the shape of `cmd_import`, which is not markdown
and must not be dragged in) and a parser that did ask the tracker.

**Red on the reverted fix** — yes, build ok (the rule put back on the list of names; the file
parses and the other four tests pass):

```
FAIL … (разборщик='документ разметки читается своими руками')
FAIL … (разборщик='строка разбирается вместе с чужим признаком')
FAIL … (разборщик='сырые строки раздела читаются как слова отчёта')
AssertionError: [] == [] : узда не увидела разборщика по виду
Ran 5 tests — FAILED (failures=3)
```

Note that `test_цитаты_распознаются_одним_местом` stayed **green** under that mutation — which
is the finding, stated as a measurement.

### T1-035 · low · `a/` and `b/` are accepted as prefixes, so a real `a/` directory closes the gate

**Reproduced first** on a twelve-row matrix of `names_file`:

```
BAD '- a/src/api.ts'  vs 'src/api.ts'  -> True (want False) — a real a/ directory must not close src/
mismatches: 1
```

**What was done** → `525b01f`. `./` stays accepted everywhere — it cannot be a real path. `a/`
and `b/` are read as a diff prefix only after a diff header marker on the same line
(`DIFF_HEADER`: `diff --git`, `---`, `+++`), where they cannot mean a directory. The marker is
looked for anywhere on the line, not only at its start, because a report pastes a header
inside a list item (`- --- a/src/api.ts`) — the form the previous round's test was written
against, which still passes.

**Which test catches it** — `ReportShapeTest.test_каталог_a_не_закрывает_ворота_за_файл_которого_никто_не_читал`
(forbidden: a block owning both `src/api.ts` and `a/src/api.ts`, a report naming only the
second — `check` exit 1 and `src/api.ts` named as missing) and
`test_заголовок_диффа_в_том_же_дереве_по_прежнему_называет_файл` (allowed: in the same tree, a
pasted `diff --git a/src/api.ts b/src/api.ts` still names it — `check` exit 0). The two tests
of the previous round hold the `./` and `docs/`/`lib/a/` directions unchanged.

**Red on the reverted fix** — yes, build ok:

```
AssertionError: 0 != 1        <- the gate green on a file nobody read
Ran 2 tests — FAILED (failures=1)   <- the allowed direction green in both, as it must be
```

### T1-036 · low · `run-role.sh` dies on the truncated stream `axes.py` was taught to survive

**Reproduced first** on a stream whose last line is `{"type":"assis`:

```
axes.py --journal rc: 0
NO RESULT EVENT — the run was killed or the stream is truncated; 1 unreadable line(s) · …
run-role.sh snippet rc: 1
json.decoder.JSONDecodeError: Unterminated string starting at: line 1 column 9 (char 8)
```

**What was done** → `02cfa59`. Two things, and both are named here because both are needed:

1. **One reader for the stream.** `axes.py` gained `--reply` (every result event's answer, in
   order, capped at `REPLY_CHARS`), and the inline `json.loads` loop in `run-role.sh` is gone.
   The second reader did not know what the first one already handled.
2. **The script's exit code is the run's.** Everything after `claude` is reporting, and under
   `set -euo pipefail` any of it — `axes.py`, `$REVIEW log` — could abort the script before
   `exit $RC` ran. A `trap 'exit $RC' EXIT` installed right after the run keeps the ending
   the run's ending, which is what anything scripted on top of `run-role.sh` reads.

**Which test catches it** — `SpendTest.test_обрезанный_поток_не_роняет_запуск_роли` (forbidden:
a stub that exits 143 leaving a half-written line — exit code 143, no traceback, the journal
line carries both `RUN FAILED` and `unreadable line`);
`test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона` (forbidden: a `$REVIEW log` that
exits 3 does not turn a successful run into a failed one);
`test_ответ_агента_печатается_из_целого_потока` (allowed: a whole stream still prints
`--- agent reply ---` with the agent's words, and a stream without one says so instead of
printing nothing).

**Red on the reverted fix** — yes, build ok (`bash -n` rc 0 on each mutant), one mechanism at
a time:

```
$ # the inline reader back
FAIL: test_обрезанный_поток_не_роняет_запуск_роли
FAIL: test_ответ_агента_печатается_из_целого_потока
Ran 13 tests — FAILED (failures=2)

$ # the EXIT trap removed
FAIL: test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона
Ran 13 tests — FAILED (failures=1)
```

## The class, and the guard that closes it

Three of the five findings (T1-032, T1-033 and, as its subject, T1-034) are the same class:
**a quotation read as the report's own words.** Counting the two rounds before this one, the
class has produced a fix in every round of this block — the fence, then the indent / `>` /
comment, now the nested fence and the substance gates. A list of fixed places has not held
it.

The guard is `tests/test_review.py::SourceRuleTest::test_цитаты_распознаются_одним_местом`,
and from this round it no longer works off a list of names: it finds a markdown parser by its
shape and demands that it ask the one tracker. It is shown red above on three parsers that do
not exist in the tool, and it went red **on the tool as it stood** — `acceptance_of`, a place
no finding named. That is recorded on the findings as
`--rule tests/test_review.py::SourceRuleTest::test_цитаты_распознаются_одним_местом`.

`names_file` is deliberately outside the rule and outside the class: a path is evidence of
reading wherever it is written, and a real path inside a pasted diff fence is exactly that
evidence. Its own class — a path written another way — is held by the four `names_file` tests.

## Incidental fixes

1. **`acceptance_of` pasted a quotation into the summary's cell** (`4ef5d7f`). Found by the new
   guard, not by a finding: the acceptance criterion is joined into one table cell, and a
   fenced example table inside the section came out there as a run of backticks and escaped
   column bars. Its own test:
   `ReviewToolTest.test_критерий_приёмки_в_итоге_без_вставленного_образца` — the sentence stays,
   the fence does not. Red on the reverted fix (build ok):
   `AssertionError: '```markdown' unexpectedly found in …`, and the class guard red beside it.
2. **The unreleased changelog bullet pointing at `fenced_lines`** (`2b8c7be`), in both
   languages: the function it named no longer exists, and the entry is still unreleased. Only
   the name inside the parentheses changed; no heading, no version, no released text. Held by
   nothing but the rule that a name in the changelog is a name in the code — no test, and it
   is named here for that reason.
3. **The over-long scenario of finding T1-033 trimmed** in `findings.jsonl` (`2b8c7be`, 757
   characters against the limit of 700), and `findings.md` regenerated — the same register
   bookkeeping the previous round did for T1-030, and the same cause: `import` writes a row
   that `check` then refuses, saying nothing at import time. That is the new finding round 2
   named rather than fixed, and it is still open as a finding of a different kind, not a fix
   inside someone else's.
4. **`SKILL.md` says what `axes.py --reply` is for** (`a15fa7f`). A change to a mechanism is a
   change to what an agent reads: the flag was added in `02cfa59` and the file that describes
   the scripts did not know about it. No test — the file's own rules (name, description,
   length, links one level deep) are held by `SkillFormatTest` and by `skills-ref validate`,
   both green after the edit.

## Rejected findings

None. All five were reproduced in the current code before being touched.

## Considered and deliberately not changed

- **The "manifest is empty or nearly empty" gate counts quoted characters too.** It is the
  same shape as T1-033 and was measured: a manifest of 200+ characters of pure fence passes
  it. It is not left open — the hypotheses gate refuses such a manifest on the next line
  ("the manifest has no hypotheses"), so no false state reaches `check` green — and
  tightening a character count would red an honest manifest that carries a long legitimate
  example, on reviews already running. A gate that starts refusing honest input is discovered
  by the person whose work it refuses.
- **`names_file` still reads paths inside quotations**, by the same argument as above.

## Left for acceptance

- **`restamp T1`** — the block fingerprint is stale because this round changed the block's
  files, which is what a fix phase does. As in the two rounds before it, this is the diff
  reviewer's call.
- **The hunter report's six contradictory verdicts** (T1.2, T1.3, T1.5, T1.7, T1.11, T1.12).
  Measured again — `verdict_mentions` and `section_items` run under the parser of `850ed21`
  and under this round's, over every T1 report and the manifest:

  ```
  T1-tool.hunter.md      verdicts same · hypothesis items same (15)
  T1-tool.verify.md      verdicts same · hypothesis items same (15)
  T1-tool.md             verdicts same · hypothesis items same (15)
  … (all eight documents)
  documents that changed: 0
  ```

  So no verdict of this review moves, and the contradictions are the report's own. A report
  is not code, and the fixer does not rewrite it.
