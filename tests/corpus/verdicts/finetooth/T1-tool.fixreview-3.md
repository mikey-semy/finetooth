# T1 — fix review, round 3

Range `850ed21..HEAD`, eleven commits, 15 files. Five findings closed (T1-032…T1-036), four
incidental fixes named. **Four findings: one medium, three low.** The medium one is a
regression this round introduced into the very mechanism it was fixing.

## What was checked and how

**The diff was read in full, against the code as it now stands**, not against the report.
The report's factual claims were re-measured rather than believed; where they hold, that is
said in "Checked and found correct".

**Gates run here, from the working tree:**

```
$ python3 -m unittest discover -s tests
Ran 230 tests in 233.230s
OK

$ npx skills-ref validate skills/finetooth
Valid skill: skills/finetooth
```

**Tests proven by reverting** — one mechanism at a time, `ast.parse` on the reverted
`review.py` and `bash -n` on the reverted `run-role.sh` each time, the file restored
afterwards and `git diff` verified clean:

| fix reverted | build | test that goes red |
|---|---|---|
| fence measured from the margin again (T1-032) | BUILDS | `test_ограда_внутри_пункта_списка_остаётся_оградой`, and `test_вердикт_после_вложенной_ограды_по_прежнему_вердикт` with it |
| `(?:\./\|a/\|b/)?` accepted anywhere again (T1-035) | BUILDS | `test_каталог_a_не_закрывает_ворота_за_файл_которого_никто_не_читал` (the allowed-direction test stayed green) |
| `verify_report_problem` reads raw lines again (T1-033) | BUILDS | `test_отчёт_проверяющего_из_одних_цитат_не_проводит_блок` (the allowed-direction test stayed green) |
| the `cmd_check` limits gate reads raw lines again (T1-033) | BUILDS | `test_раздел_ограничений_из_одной_цитаты_роняет_проверку` (subTest `красное=True`; `красное=False` stayed green) |
| `acceptance_of` keeps the quotation again (incidental 1) | BUILDS | `test_критерий_приёмки_в_итоге_без_вставленного_образца` |
| `trap 'exit $RC' EXIT` removed (T1-036) | `bash -n` rc 0 | `test_отказ_шага_отчёта_не_подменяет_код_возврата_прогона` |
| the inline `json.loads` reader back in `run-role.sh` (T1-036) | `bash -n` rc 0 | `test_обрезанный_поток_не_роняет_запуск_роли` and `test_ответ_агента_печатается_из_целого_потока` |

Every mutation is red, every build is intact, and in every pair the allowed-direction test
stayed green except for the fence pair, where the old code fails both (on the old parser the
quoted skeleton is a real verdict, so the second test's "not checked" conflicts with it —
the pair still proves the new behaviour, it is just not an independent pair).

**Gates checked by violation, not by reading.** Two violations appended to `review.py` in
one run — `report_headings(md)`, a markdown parser that never asks the tracker (the new
shape-based form), and `own_fence_detector(lines)`, a function with its own `FENCE` use (the
old name-based form). `SourceRuleTest` goes red on both in the same run:
`strangers=[('own_fence_detector', ['FENCE'])]`, `deaf=['report_headings',
'own_fence_detector']`. Separately, a new `problems.append(...)` gate added to `cmd_check`
with no registered test turns `GateRegistryTest.test_каждые_ворота_check_записаны_вместе_со_своим_тестом`
red. Both files restored, `git diff` clean.

**Reproduced live, with the tool, not only from the code.** R3-001 and R3-002 were each run
end to end through `init` → `coverage` → `set-status` → `check` on a throwaway repository
built with the suite's own `Stand`, and R3-001 was run through the tool at `850ed21` as well
to separate "was already so" from "this round did it". R3-004 was run through
`SpendTest._run_role` with and without the trap.

**Swept, not sampled.** `quoted_lines` at `850ed21` vs at HEAD over all 55 markdown files
tracked in this repository: **no file changes its quotation map**. The fixer's "moves no
verdict" claim holds, and it holds wider than the eight documents the report measured.
R3-001 is a trap for documents not yet written, not a change to this review's verdicts.

**What was not done.** No MSG key comparison (the diff adds no `MSG` key — every new string
is an English literal in `cmd_check` / `verify_report_problem`, which is where the tool's own
messages belong). The three acceptance tables were not rebuilt; they are the hunter's
criterion, not this role's. `claude` was never actually invoked — `run-role.sh` was exercised
with the suite's stub, which reproduces the exit code and the half-written stream line but
not the real client. The tool was not run against either of the two live projects.

## Findings

### R3-001 · medium · the nested-fence fix silently truncates a manifest again, and `check` goes green on it

**Location:** `skills/finetooth/scripts/review.py:1487`

**What is wrong:** `quoted_lines` now decides whether a `` ``` `` line opens a fence by
`indent <= content_col + FENCE_SLACK`, and `content_col` is raised by any list marker on a
line the tracker has not marked quoted. When the *opening* fence of an example is indented
four or more spaces past the current content column with no blank line before it, it is
correctly not an indented code block (an indented code block cannot interrupt a paragraph)
and so no fence opens — but the example's first inner line is normally a list item
(`- H1.1 — проверена`), and that list item raises `content_col`. The example's *closing*
`` ``` `` then falls inside the new, larger window and is read as an **opening** fence. It
never closes, so every line from there to the end of the document is marked quoted and
vanishes from `section_body`, `section_items_full`, `verdict_mentions` and `demote`.

Before this round `FENCE` was anchored at `^\s{0,3}`: neither line matched, and the document
continued intact. The window became relative in `74c7522`, and the asymmetry came with it.

**Failure scenario:** a manifest whose Hypotheses section reads

```
## Гипотезы

1. Гипотеза номер 1: … Инструмент печатает вердикт так:
       ```
       - H1.1 — проверена
       ```
2. Гипотеза номер 2: …
3. Гипотеза номер 3: …
4. Гипотеза номер 4: …
```

Run end to end on a throwaway repository, the same manifest and the same one-verdict hunter
report through both tools:

```
=== 850ed21 (before this round)
  H1.1  checked      H1.2  NO VERDICT   H1.3  NO VERDICT   H1.4  NO VERDICT
  closed 1/4
  check rc=1 · H1: 3 of 4 hypotheses without a verdict (H1.2, H1.3, H1.4)

=== HEAD
  H1.1  checked
  closed 1/1
  check rc=0 · review state is consistent
```

Three hypotheses disappear from the count, from `check` and from `hypotheses_sha`. The same
input with the example at four spaces under a plain sentence (content column 0) loses the
section entirely: `section_items_full` returns 3 items on the old parser and 0 on the new.

**Why it is a defect:** it is the invariants' first and most serious class — a way to make
`check` pass on a state that is wrong — and it is, line for line, the failure the block
already has a closed finding for: T1-004, "a manifest with four hypotheses yielded two,
`check` demanded two verdicts, got them and passed, and the fingerprint covered only the
truncated text". It also breaks fingerprint invariant 6: `hypotheses_sha` no longer covers
the whole of its subject. Filed medium to match T1-004, which is the identical shape; it sits
at the top of that band, not the bottom.

**Introduced by this round or present before:** **introduced by this round**, commit
`74c7522`. Measured in both directions above.

**Confidence:** confirmed

### R3-002 · low · the other address of T1-035: a diff header closes the gate for a real `a/…` file nobody read

**Location:** `skills/finetooth/scripts/review.py:2727`

**What is wrong:** T1-035 was fixed in one direction only. `a/` is no longer read as a
prefix when the report names `a/src/api.ts` and the block owns `src/api.ts` — but nothing
was done about the mirror case, where a diff header names `src/api.ts` and the block owns a
real file called `a/src/api.ts`. The `said` branch matches the literal substring
`a/src/api.ts` inside `--- a/src/api.ts`, and on a diff header line those two characters are
a prefix, not a directory.

**Failure scenario:** reproduced end to end. A repository with both `src/api.ts` and
`a/src/api.ts`, a block owning both, `named_files: true`, and a hunter report whose only
file evidence is a pasted

```diff
diff --git a/src/api.ts b/src/api.ts
```

`check` exits **0** and says nothing about `a/src/api.ts`, which no report names and nobody
read. The fixer's own allowed-direction test
(`test_заголовок_диффа_в_том_же_дереве_по_прежнему_называет_файл`) is built on exactly this
tree and passes for the same reason.

**Why it is a defect:** rule 5 — the fix goes to every address. It is the same sentence from
T1-035's own claim ("a real `a/` directory closes the gate for a file nobody read") with the
two paths swapped, and the named-files gate is one of the gates that decide whether a block
was really read.

**Introduced by this round or present before:** **present before** — the `said` branch is
unchanged. The round narrowed one direction of the defect and left the other standing.

**Confidence:** confirmed

### R3-003 · low · the rewritten quotation guard does not see the two gates it is recorded against

**Location:** `tests/test_review.py:4050`

**What is wrong:** the guard was rewritten to find a markdown parser by its shape, and
`T1-032` and `T1-033` carry `rule:
tests/test_review.py::SourceRuleTest.test_цитаты_распознаются_одним_местом` in the register,
with the fix report stating that `section_body`'s raw-lines exception "is exactly the hole
T1-033 fell through". Measured, it is not. With `unquoted` taken back out of either gate the
guard stays green:

```
verify_report_problem reads raw lines again: GREEN (guard blind)  deaf=[] strangers=[]
cmd_check limits gate reads raw lines again: GREEN (guard blind)  deaf=[] strangers=[]
markdown parser whose document parameter is named `text`: GREEN (guard blind)
```

`verify_report_problem(rep, has_findings)` has no `md` parameter, names no markup pattern,
calls no section reader and zips nothing, so it is never even considered a markdown parser.
`cmd_check` can never be flagged at all: it calls `verdicts_in`, `section_items` and
`verdict_conflicts`, which ask the tracker, so it is in `asks` by construction — and
`cmd_check` is where most of the tool's gates live.

**Failure scenario:** a later editor adds a substance gate to `cmd_check` — the natural place
for one — that reads a report's raw lines, or writes a report parser whose document parameter
is called `text` or `doc` instead of `md`. The guard is green by construction; only a
hand-written behaviour test would catch it, which is the situation the guard was rewritten
to end. The two behaviour tests added this round do still hold the two gates, so nothing is
untested today; what is wrong is that the class is recorded as closed by a rule that does not
reach it.

**Why it is a defect:** invariant 2 and the kit's own rule that a class repeating three times
is closed by a guard rather than by three fixes. It is also the discrepancy rule: the report
and the changelog claim a coverage the code does not have. Worth saying plainly — the
quotation class has now produced a defect in all three rounds, and every one of them
(T1-001, T1-004, T1-028, T1-032, and R3-001 above) lived in **what the tracker itself does**,
while the guard only watches **who calls it**. It has never been red on one of the class's
real defects.

**Introduced by this round or present before:** the blindness is **present before** (the
name-based guard could not reach these places either); the claim that it is now covered is
new this round.

**Confidence:** confirmed

### R3-004 · low · the EXIT trap turns a lost journal line into a successful run

**Location:** `skills/finetooth/assets/run-role.sh:47`

**What is wrong:** `trap 'exit $RC' EXIT` makes the script's code the run's code whatever the
reporting steps do — which is right, and is what T1-036 asked for. But it also makes a
*failed* reporting step invisible to anything that reads the exit code, and under `set -e`
the failure aborts the rest of the reporting with it, so the agent's reply is never printed
either.

**Failure scenario:** measured, with and without the trap, on a successful run whose
`$REVIEW log` refuses (a block id the state does not know, `docs/review/` not initialised, a
read-only checkout):

```
HEAD (trap installed)            rc=0  stderr='log failed'  journal line written: False
without the trap (before)        rc=3  stderr='log failed'  journal line written: False
```

An operator or a wrapper script reads exit 0 and a clean run; the spend line for that run is
never written, and the journal — "the only memory the next session has" — has a silent hole
where a 35-minute run should be. The same happens if `axes.py` on line 49 fails for any
reason after a successful `claude`.

**Why it is a defect:** the invariant that state lives on disk and the journal is the next
session's memory. The fix is right in intent; what is missing is the loud half — nothing
tells the operator, in the exit code or in stdout, that the record was lost. Rule 3 applies:
there is a test that a report failure does not change the run's code, and none that the
operator is still told the report failed.

**Introduced by this round or present before:** **introduced by this round**, commit
`02cfa59`.

**Confidence:** confirmed

## Checked and found correct

- **T1-036, the one reader of the stream.** `axes.py` was run over four streams a killed or
  never-started run leaves — empty, one garbage line, a half-written last line, only a
  `system` event — in all three modes (no flag, `--journal`, `--reply`). Twelve runs, every
  one exit 0, no traceback, every one naming the truncation. `--reply` on a stream with no
  result event says so rather than printing nothing. The fix is real and the hardening is
  wider than the finding asked for.
- **`REPLY_CHARS = 4000` and `FENCE_SLACK = CODE_INDENT - 1`** both carry their source in a
  comment above them (an operator's terminal; CommonMark 4.5, derived from `CODE_INDENT`).
  Invariant 8 holds, and the constant-source rule in `SourceRuleTest` is green.
- **A mechanism change is a prompt change.** The `unquoted` gates are matched by edits to
  `hunter.md`, `hunter.ru.md`, `verify.md` and `verify.ru.md` — all four, both languages —
  and `test_шаблоны_ролей_говорят_что_цитата_не_считается_нигде` holds them. The two gates
  that changed are exactly the two roles whose templates were edited; no third address was
  found by grep.
- **No `MSG` key was added on one side only.** The diff adds no `MSG` entry at all; every new
  string is an English literal in the tool's own messages, which is where the invariant puts
  them. Each of the three reworded refusals names where the answer belongs ("as an ordinary
  line and not inside a fence or a quotation"), so invariant 3 holds.
- **Every incidental fix is named in the report** with its own line, and each was checked
  against the diff: `acceptance_of` (with its own test, red on revert), the changelog bullet
  naming a function that no longer exists (in both languages, inside `## [Unreleased]`, only
  the name inside the parentheses changed), the over-long T1-033 scenario trimmed in the
  register (substance preserved — only a quoted docstring was dropped), and the `SKILL.md`
  line about `--reply`. Nothing in the diff is unaccounted for.
- **`names_file` narrowing does not refuse the honest forms it used to accept.** A
  twelve-row matrix was run: `./src/api.ts`, `--- a/src/api.ts`, `+++ b/src/api.ts`,
  `diff --git …`, and the previous round's `- --- a/src/api.ts` inside a list item all still
  name the file; `docs/src/api.ts` and `lib/a/src/api.ts` still do not. One narrowing was
  noticed and is **not** filed: a diff header wrapped in a code span
  (``- `--- a/src/api.ts` ``) is no longer recognised, because `DIFF_HEADER` wants start-of-line
  or whitespace before the marker and a backtick is neither. It is not a defect — a report
  that quotes a header that way has the path in its own list too, and `./` still works
  everywhere — but it is the kind of thing the next narrowing of this regex should not
  compound.
- **The "manifest is nearly empty" gate and `names_file` inside quotations** were both left
  alone deliberately and both arguments in the report hold up: the hypotheses gate refuses a
  fence-only manifest on the next line, and a path is evidence of reading wherever it is
  written.

## Is another round needed

**Yes — one more, and it should be narrow.**

The project did get better. All five findings of round 2 are genuinely closed, every claimed
mutation is red with the build intact, both directions are tested for each fix, the
`run-role.sh` / `axes.py` hardening goes wider than the finding asked, and the quotation
guard is measurably stronger than the list of names it replaced. Two hundred and thirty tests
pass, the skill validates, and the round moved no verdict of this review anywhere in the
repository's 55 markdown files.

But R3-001 has to be closed before the block is, and it is not a matter of taste: `check`
prints "review state is consistent" on a manifest three of whose four hypotheses it never
saw, and it did not do that before this round. One medium, product behaviour, `check` green
on a false state.

**Of the four findings: four are inside code this round changed, none outside it.** That
number is the honest signal and it should be read as one. Round 2 found five, round 3 fixed
five and reopened the class it was closing. The loop is not in the reviewing; it is in the
method — `quoted_lines` is being extended one observed shape at a time (fences, then `~~~`,
then indent/`>`/comment, then the list column), and each extension buys a new asymmetry
because nothing states what the function is supposed to compute. R3-003 says the same thing
from the other side: the guard watches who calls the tracker, and every real defect of this
class has been inside the tracker.

So: one more round, scoped to R3-001, and the fixer should be told plainly that another
special case is the wrong shape of answer — what is missing is a statement of the invariant
(a quotation map that cannot swallow the tail of a document; a fence that opens and one that
closes measured by the same rule) and a test that holds it over generated inputs rather than
over the three shapes someone happened to write down. R3-002 is a two-line completion of a
fix already made and should go in the same round. R3-003 and R3-004 are small and can ride
along, but neither should by itself buy a fifth round: if round 4 closes R3-001 and R3-002
and finds nothing new in the tracker, the block is done.
